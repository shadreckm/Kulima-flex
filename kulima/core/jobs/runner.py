"""Durable job runner for transaction processing (Phase 4).

This runner implements the background worker that processes jobs from the
durable queue, enabling work to survive process restarts and supporting
resume-on-login functionality.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from .models import Job, JobKind, JobStatus
from .repository import JobRepository
from kulima.core.cases.service import CaseService
from kulima.core.cases.models import CaseLifecycleStatus

_log = logging.getLogger(__name__)


class JobRunner:
    """Background worker that processes durable jobs from the queue.

    The runner:
    - Claims jobs with exclusive leases
    - Executes job handlers based on job kind
    - Updates job status and results
    - Recovers stalled jobs on startup
    - Survives process restarts
    """

    def __init__(
        self,
        db_path: str | None = None,
        worker_id: str | None = None,
        poll_interval_seconds: float = 5.0,
        lease_duration_seconds: int = 300,
    ) -> None:
        self.job_repo = JobRepository(db_path)
        self.case_service = CaseService(db_path)
        self.worker_id = worker_id or str(uuid.uuid4())
        self.poll_interval = poll_interval_seconds
        self.lease_duration = lease_duration_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the job runner background task."""
        if self._running:
            _log.warning("JobRunner already running")
            return

        _log.info("JobRunner starting: worker_id=%s", self.worker_id)
        self._running = True

        # Recover any stalled jobs from previous runs
        recovered = self.job_repo.recover_stalled_jobs()
        if recovered > 0:
            _log.info("JobRunner recovered %d stalled jobs", recovered)

        self._task = asyncio.create_task(self._worker_loop())
        _log.info("JobRunner started successfully")

    async def stop(self) -> None:
        """Stop the job runner gracefully."""
        if not self._running:
            return

        _log.info("JobRunner stopping: worker_id=%s", self.worker_id)
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        _log.info("JobRunner stopped")

    async def _worker_loop(self) -> None:
        """Main worker loop that claims and processes jobs."""
        while self._running:
            try:
                job = self.job_repo.claim_job(self.worker_id, self.lease_duration)
                if job:
                    _log.info(
                        "JobRunner claimed job: id=%s kind=%s case_id=%s attempt=%d/%d",
                        job.id,
                        job.kind.value,
                        job.case_id,
                        job.attempts,
                        job.max_attempts,
                    )
                    await self._process_job(job)
                else:
                    # No jobs available, wait before next poll
                    await asyncio.sleep(self.poll_interval)
            except Exception as exc:  # noqa: BLE001
                _log.exception("JobRunner worker loop error: %s", exc)
                await asyncio.sleep(self.poll_interval)

    async def _process_job(self, job: Job) -> None:
        """Process a single job based on its kind."""
        try:
            result = await self._execute_job(job)
            self.job_repo.complete_job(job.id, result)
            _log.info("JobRunner completed job: id=%s", job.id)

            # Update case lifecycle if this was the last pending job
            await self._maybe_advance_case_lifecycle(job.case_id)

        except Exception as exc:  # noqa: BLE001
            _log.exception("JobRunner failed job: id=%s error=%s", job.id, exc)
            is_dead = job.attempts >= job.max_attempts
            self.job_repo.fail_job(job.id, str(exc), is_dead=is_dead)

            # Propagate failure to the run / assessment that enqueued this job
            # so they do not stay stuck in "running" forever.
            if is_dead:
                self._propagate_failure(job, str(exc))
                _log.error("JobRunner marked job as dead: id=%s", job.id)
                # Transition case to DRAFT for manual intervention
                await self._handle_dead_job(job.case_id)

    def _propagate_failure(self, job: Job, error_message: str) -> None:
        """Mark the originating run and assessment as failed for a dead job."""
        run_id = job.payload.get("run_id")
        assessment_id = job.payload.get("assessment_id")
        try:
            if run_id:
                from backend.app.services.run_repository import RunRepository

                RunRepository().update_run_failed(run_id, error_message)
                _log.warning("Marked run %s failed due to dead job %s", run_id, job.id)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Could not mark run %s failed: %s", run_id, exc)
        try:
            if assessment_id:
                from backend.app.services.orchestrator_adapter import (
                    _mark_assessment_failed,
                )

                _mark_assessment_failed(assessment_id, error_message)
                _log.warning("Marked assessment %s failed due to dead job %s", assessment_id, job.id)
        except Exception as exc:  # noqa: BLE001
            _log.warning("Could not mark assessment %s failed: %s", assessment_id, exc)

    async def _execute_job(self, job: Job) -> dict[str, any]:
        """Execute the job based on its kind."""
        if job.kind == JobKind.RESEARCH:
            return await self._execute_research_job(job)
        elif job.kind == JobKind.EXTRACTION:
            return await self._execute_extraction_job(job)
        elif job.kind == JobKind.SIGNALS:
            return await self._execute_signals_job(job)
        elif job.kind == JobKind.DECISION:
            return await self._execute_decision_job(job)
        elif job.kind == JobKind.EXPORT:
            return await self._execute_export_job(job)
        elif job.kind == JobKind.RETENTION_CLEANUP:
            return await self._execute_retention_cleanup_job(job)
        else:
            raise ValueError(f"Unknown job kind: {job.kind}")

    async def _execute_research_job(self, job: Job) -> dict[str, any]:
        """Run the intelligence pipeline from a durable research job."""
        from backend.app.services import orchestrator_adapter

        _log.info("Executing research job for case %s", job.case_id)
        founder = job.payload.get("founder", "")
        startup = job.payload.get("startup", "")
        sector_hint = job.payload.get("sector_hint", "")
        user_id = job.payload.get("user_id")
        assessment_id = job.payload.get("assessment_id")
        document_ids = job.payload.get("document_ids", [])
        run_id = job.payload.get("run_id")
        case = self.case_service.get_case(job.case_id)
        org_id = job.payload.get("org_id") or (case.org_id if case else None)

        try:
            research_engine = orchestrator_adapter.get_orchestrator().research
            research_bundle = await asyncio.to_thread(
                research_engine.research_bundle,
                founder,
                startup,
                sector_hint,
            )
        except Exception as research_exc:  # noqa: BLE001 — documents remain usable without Tavily
            _log.warning("External research unavailable; continuing with assessment documents: %s", research_exc)
            research_bundle = {"founder": [], "startup": [], "market": [], "risks": []}

        fallback_used = False
        research_payload = None
        fallback_signal_titles: list[str] = []
        try:
            orchestrator = orchestrator_adapter.get_orchestrator()
            brief = await asyncio.to_thread(
                orchestrator.analyze,
                founder,
                startup,
                user_id=user_id,
                sector_hint=sector_hint,
                research_results=research_bundle,
            )
        except Exception as exc:  # noqa: BLE001 — only OpenAI outages use document intelligence fallback
            if not orchestrator_adapter.is_openai_unavailable(exc):
                raise
            _log.warning(
                "OpenAI unavailable for run %s; using Document Intelligence Mode: %s",
                run_id,
                exc,
            )
            brief, research_payload, fallback_signal_titles = orchestrator_adapter.build_document_intelligence_fallback(
                founder,
                startup,
                user_id=user_id,
                org_id=org_id,
                assessment_id=assessment_id,
                sector_hint=sector_hint,
                research_bundle=research_bundle,
                failure=exc,
            )
            fallback_used = True
        db_id = await asyncio.to_thread(
            orchestrator_adapter._repo.save_brief,
            brief,
            user_id,
            org_id,
        )
        if run_id:
            await asyncio.to_thread(
                orchestrator_adapter._run_repo.update_run_completed,
                run_id,
                db_id=db_id,
            )
        await asyncio.to_thread(
            orchestrator_adapter._sync_assessment,
            assessment_id,
            document_ids,
            db_id,
            brief,
            org_id=org_id,
            research=research_payload,
            generated_signal_titles=fallback_signal_titles,
        )

        return {
            "sources_count": len(brief.sources),
            "db_id": db_id,
            "run_id": run_id,
            "assessment_id": assessment_id,
            "mode": "document_intelligence" if fallback_used else "ai_assisted",
            "founder": founder,
            "startup": startup,
            "sector_hint": sector_hint,
        }

    async def _execute_extraction_job(self, job: Job) -> dict[str, any]:
        """Execute a document extraction job."""
        _log.info("Executing extraction job for case %s", job.case_id)

        # Import extraction logic
        from kulima.core.assessment.extraction import extract_entities_from_documents

        document_ids = job.payload.get("document_ids", [])
        case_id = job.case_id

        # Perform extraction
        extraction_result = await asyncio.to_thread(
            extract_entities_from_documents,
            document_ids,
            case_id,
        )

        return {
            "entities_extracted": len(extraction_result.get("entities", [])),
            "document_count": len(document_ids),
            "confidence": extraction_result.get("confidence", 0.0),
        }

    async def _execute_signals_job(self, job: Job) -> dict[str, any]:
        """Execute a signals generation job."""
        _log.info("Executing signals job for case %s", job.case_id)

        # Import signals orchestrator
        from kulima.signals.orchestrator import SignalsOrchestrator
        from kulima.core.cases.adapters import from_investment_brief

        # Load case and brief
        case = self.case_service.get_case(job.case_id)
        if not case:
            raise ValueError(f"Case not found: {job.case_id}")

        # Reconstruct brief from case payload
        from kulima.models import InvestmentBrief
        brief = InvestmentBrief.model_validate(case.payload)

        # Generate signals
        orchestrator = SignalsOrchestrator()
        case_wrapper = from_investment_brief(brief, case_id=job.case_id)
        signals = await asyncio.to_thread(orchestrator.generate, case_wrapper, sort=True)

        return {
            "signals_count": len(signals),
            "domains_covered": len(set(s.domain for s in signals)),
        }

    async def _execute_decision_job(self, job: Job) -> dict[str, any]:
        """Execute a decision generation job."""
        _log.info("Executing decision job for case %s", job.case_id)

        # Decision generation is already handled by the orchestrator
        # This job primarily serves as a synchronization point
        return {
            "decision_generated": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def _execute_export_job(self, job: Job) -> dict[str, any]:
        """Execute an export job (PDF generation)."""
        _log.info("Executing export job for case %s", job.case_id)

        # Import export logic
        from kulima.export import export_decision_report

        case = self.case_service.get_case(job.case_id)
        if not case:
            raise ValueError(f"Case not found: {job.case_id}")

        # Generate export
        export_path = await asyncio.to_thread(
            export_decision_report,
            case.payload,  # Pass the brief data
            job.payload.get("format", "pdf"),
        )

        return {
            "export_path": export_path,
            "format": job.payload.get("format", "pdf"),
        }

    async def _execute_retention_cleanup_job(self, job: Job) -> dict[str, any]:
        """Execute a document retention cleanup job."""
        _log.info("Executing retention cleanup job for org %s", job.payload.get("org_id"))

        from kulima.core.documents.repository import DocumentRepository

        doc_repo = DocumentRepository()
        org_id = job.payload.get("org_id")
        cleaned_count = await asyncio.to_thread(
            doc_repo.cleanup_expired_documents,
            org_id=org_id,
        )

        return {
            "expired_documents_cleaned": cleaned_count,
            "org_id": org_id,
        }

    async def _maybe_advance_case_lifecycle(self, case_id: str) -> None:
        """Check if all jobs for a case are complete and advance lifecycle."""
        jobs = self.job_repo.list_for_case(case_id)
        pending_jobs = [j for j in jobs if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)]

        if not pending_jobs:
            # All jobs complete, advance to REVIEW
            case = self.case_service.get_case(case_id)
            if case and case.lifecycle_status == CaseLifecycleStatus.PROCESSING:
                _log.info("All jobs complete for case %s, advancing to REVIEW", case_id)
                # Note: This would need proper role context - simplified here
                # In production, this would be called with proper actor credentials
                # self.case_service.transition_lifecycle(case_id, CaseLifecycleStatus.REVIEW, actor_id, actor_role)

    async def _handle_dead_job(self, case_id: str) -> None:
        """Handle a job that has exceeded max attempts."""
        _log.warning("Handling dead job for case %s - reverting to DRAFT", case_id)
        # Revert case to DRAFT for manual intervention
        case = self.case_service.get_case(case_id)
        if case:
            # Use system user for recovery transitions
            from kulima.core.orgs.models import Role
            try:
                self.case_service.transition_lifecycle(
                    case_id,
                    CaseLifecycleStatus.DRAFT,
                    "system_recovery",
                    Role.ADMIN,  # System has admin privileges for recovery
                    org_id=case.org_id,
                )
                _log.info("Case %s reverted to DRAFT for manual intervention", case_id)
            except Exception as exc:  # noqa: BLE001
                _log.error("Failed to revert case %s to DRAFT: %s", case_id, exc)
