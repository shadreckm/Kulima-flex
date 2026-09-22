"""Enterprise Case service for lifecycle and workflow management (Phase 4).

This service implements the business logic for:
- Case lifecycle state machine (Draft → Processing → Review → Decision Ready → Exported → Archived)
- Role-based workflow enforcement
- Workspace management
- Case-assessment linkage
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from kulima.core.orgs.models import Role, Permission, role_has_permission
from kulima.core.audit import record_event
from .models import (
    Case,
    CaseType,
    CaseLifecycleStatus,
    WorkspaceType,
    CaseSubject,
)
from .repository import CaseRepository
from kulima.core.assessment.models import AssessmentType

_log = logging.getLogger(__name__)


# Mapping from AssessmentType to WorkspaceType
ASSESSMENT_TO_WORKSPACE: dict[AssessmentType, WorkspaceType] = {
    AssessmentType.STARTUP: WorkspaceType.STARTUP,
    AssessmentType.NGO: WorkspaceType.NGO,
    AssessmentType.GOVERNMENT_PROGRAM: WorkspaceType.GOVERNMENT_PROGRAM,
    AssessmentType.DEVELOPMENT_PROGRAM: WorkspaceType.DEVELOPMENT_PROGRAM,
    AssessmentType.TOURISM_SME: WorkspaceType.TOURISM_SME,
    AssessmentType.ACCELERATOR: WorkspaceType.STARTUP,  # Legacy alias
}


class CaseService:
    """Business logic for enterprise case management."""

    def __init__(self, db_path: str | None = None) -> None:
        self.repo = CaseRepository(db_path)

    def create_case(
        self,
        assessment_id: str,
        assessment_type: AssessmentType,
        subject: CaseSubject,
        org_id: str,
        created_by: str,
        assignee_id: str | None = None,
    ) -> Case:
        """Create a new case from an assessment context.

        The case becomes the enterprise aggregate root for the assessment,
        with lifecycle state machine and workspace binding.
        """
        workspace_type = ASSESSMENT_TO_WORKSPACE.get(assessment_type, WorkspaceType.STARTUP)

        case = Case(
            id=str(uuid.uuid4()),
            case_type=CaseType.INVESTMENT,  # Default to investment for FLEX
            subject=subject,
            workspace_type=workspace_type,
            lifecycle_status=CaseLifecycleStatus.DRAFT,
            assessment_id=assessment_id,
            org_id=org_id,
            assignee_id=assignee_id or created_by,
            created_by=created_by,
            updated_at=datetime.now(timezone.utc),
        )
        saved_case = self.repo.save(case)

        # Record audit event for case creation
        record_event(
            "case.created",
            org_id=org_id,
            user_id=created_by,
            case_id=case.id,
            assessment_id=assessment_id,
            metadata={
                "case_type": case.case_type.value,
                "workspace_type": workspace_type.value,
                "assessment_type": assessment_type.value,
                "assignee_id": case.assignee_id,
            },
        )

        return saved_case

    def get_case(self, case_id: str, org_id: str | None = None) -> Optional[Case]:
        """Retrieve a case with workspace scoping."""
        return self.repo.get(case_id, org_id=org_id)

    def get_case_by_assessment(self, assessment_id: str, org_id: str | None = None) -> Optional[Case]:
        """Resolve the case for a given assessment context."""
        return self.repo.get_by_assessment_id(assessment_id, org_id=org_id)

    def transition_lifecycle(
        self,
        case_id: str,
        new_status: CaseLifecycleStatus,
        actor_id: str,
        actor_role: Role,
        org_id: str | None = None,
    ) -> Optional[Case]:
        """Transition a case to a new lifecycle status with role enforcement.

        Enforces the state machine and role-based workflow rules:
        - DRAFT → PROCESSING: Owner, Admin, Reviewer
        - PROCESSING → REVIEW: Automatic when engines complete
        - REVIEW → DECISION_READY: Owner, Admin only
        - DECISION_READY → EXPORTED: Owner, Admin, Reviewer
        - EXPORTED → ARCHIVED: Owner, Admin only
        - Any → DRAFT: Owner, Admin (reopen for editing)
        """
        case = self.repo.get(case_id, org_id=org_id)
        if case is None:
            _log.warning("Case not found for transition: %s", case_id)
            return None

        # Validate transition is legal
        if not self._is_valid_transition(case.lifecycle_status, new_status):
            _log.warning(
                "Invalid lifecycle transition: %s → %s for case %s",
                case.lifecycle_status.value,
                new_status.value,
                case_id,
            )
            return None

        # Validate role permissions for this transition
        if not self._role_can_transition(actor_role, case.lifecycle_status, new_status):
            _log.warning(
                "Role %s not authorized for transition %s → %s",
                actor_role.value,
                case.lifecycle_status.value,
                new_status.value,
            )
            return None

        # Perform transition
        updated_case = self.repo.update_lifecycle(case_id, new_status, actor_id, org_id=org_id)
        if updated_case:
            _log.info(
                "Case %s transitioned %s → %s by %s",
                case_id,
                case.lifecycle_status.value,
                new_status.value,
                actor_id,
            )
            # Record audit event for lifecycle transition
            record_event(
                "case.lifecycle_changed",
                org_id=org_id,
                user_id=actor_id,
                case_id=case_id,
                metadata={
                    "from_status": case.lifecycle_status.value,
                    "to_status": new_status.value,
                    "transition_by": actor_id,
                    "transition_role": actor_role.value,
                },
            )
        return updated_case

    def assign_case(
        self,
        case_id: str,
        assignee_id: str,
        actor_id: str,
        actor_role: Role,
        org_id: str | None = None,
    ) -> Optional[Case]:
        """Assign a case to a different user."""
        case = self.repo.get(case_id, org_id=org_id)
        if case is None:
            return None

        # Only Owner and Admin can reassign
        if not role_has_permission(actor_role, Permission.MANAGE_USERS):
            _log.warning("User %s not authorized to reassign case %s", actor_id, case_id)
            return None

        case.assignee_id = assignee_id
        case.updated_at = datetime.now(timezone.utc)
        updated_case = self.repo.save(case)

        # Record audit event for case assignment
        record_event(
            "case.assigned",
            org_id=org_id,
            user_id=actor_id,
            case_id=case_id,
            metadata={
                "previous_assignee": case.assignee_id,
                "new_assignee": assignee_id,
                "assigned_by": actor_id,
            },
        )

        return updated_case

    def set_reviewer(
        self,
        case_id: str,
        reviewer_id: str,
        actor_id: str,
        actor_role: Role,
        org_id: str | None = None,
    ) -> Optional[Case]:
        """Set the reviewer for a case in REVIEW state."""
        case = self.repo.get(case_id, org_id=org_id)
        if case is None:
            return None

        # Only Owner and Admin can assign reviewers
        if not role_has_permission(actor_role, Permission.MANAGE_USERS):
            _log.warning("User %s not authorized to set reviewer for case %s", actor_id, case_id)
            return None

        case.reviewer_id = reviewer_id
        case.updated_at = datetime.now(timezone.utc)
        updated_case = self.repo.save(case)

        # Record audit event for reviewer assignment
        record_event(
            "case.reviewer_assigned",
            org_id=org_id,
            user_id=actor_id,
            case_id=case_id,
            metadata={
                "previous_reviewer": case.reviewer_id,
                "new_reviewer": reviewer_id,
                "assigned_by": actor_id,
            },
        )

        return updated_case

    def list_my_work(self, user_id: str, org_id: str) -> list[Case]:
        """Return cases assigned to the user in DRAFT or PROCESSING states."""
        return self.repo.list_for_org(
            org_id,
            lifecycle_status=None,  # We'll filter in query
            assignee_id=user_id,
        )

    def list_team_work(self, user_id: str, org_id: str) -> list[Case]:
        """Return cases assigned to other team members (not archived)."""
        all_cases = self.repo.list_for_org(org_id)
        return [c for c in all_cases if c.assignee_id != user_id and c.lifecycle_status != CaseLifecycleStatus.ARCHIVED]

    def list_pending_reviews(self, user_id: str, org_id: str, user_role: Role) -> list[Case]:
        """Return cases in REVIEW state awaiting the user or Manager+."""
        if user_role in (Role.OWNER, Role.ADMIN):
            # Managers see all REVIEW cases
            return self.repo.list_for_org(org_id, lifecycle_status=CaseLifecycleStatus.REVIEW)
        else:
            # Reviewers see only cases assigned to them for review
            return [c for c in self.repo.list_for_org(org_id, lifecycle_status=CaseLifecycleStatus.REVIEW) if c.reviewer_id == user_id]

    def list_completed(self, org_id: str) -> list[Case]:
        """Return cases in DECISION_READY or EXPORTED states."""
        return [
            c
            for c in self.repo.list_for_org(org_id)
            if c.lifecycle_status in (CaseLifecycleStatus.DECISION_READY, CaseLifecycleStatus.EXPORTED)
        ]

    def list_archived(self, org_id: str) -> list[Case]:
        """Return archived cases."""
        return self.repo.list_for_org(org_id, lifecycle_status=CaseLifecycleStatus.ARCHIVED)

    def get_active_for_user(self, user_id: str, org_id: str | None = None) -> list[Case]:
        """Return cases in PROCESSING or REVIEW states assigned to the user."""
        return self.repo.list_active_for_user(user_id, org_id=org_id)

    @staticmethod
    def _is_valid_transition(current: CaseLifecycleStatus, new: CaseLifecycleStatus) -> bool:
        """Validate lifecycle state machine transitions."""
        valid_transitions = {
            CaseLifecycleStatus.DRAFT: {CaseLifecycleStatus.PROCESSING},
            CaseLifecycleStatus.PROCESSING: {CaseLifecycleStatus.REVIEW, CaseLifecycleStatus.DRAFT},
            CaseLifecycleStatus.REVIEW: {CaseLifecycleStatus.DECISION_READY, CaseLifecycleStatus.DRAFT},
            CaseLifecycleStatus.DECISION_READY: {CaseLifecycleStatus.EXPORTED, CaseLifecycleStatus.DRAFT},
            CaseLifecycleStatus.EXPORTED: {CaseLifecycleStatus.ARCHIVED, CaseLifecycleStatus.DRAFT},
            CaseLifecycleStatus.ARCHIVED: {CaseLifecycleStatus.DRAFT},  # Reopen
        }
        return new in valid_transitions.get(current, set())

    @staticmethod
    def _role_can_transition(role: Role, current: CaseLifecycleStatus, new: CaseLifecycleStatus) -> bool:
        """Check if a role can perform a specific lifecycle transition."""
        # DRAFT → PROCESSING: All roles except Viewer
        if current == CaseLifecycleStatus.DRAFT and new == CaseLifecycleStatus.PROCESSING:
            return role != Role.VIEWER

        # PROCESSING → REVIEW: Automatic (no role check needed, system-triggered)
        if current == CaseLifecycleStatus.PROCESSING and new == CaseLifecycleStatus.REVIEW:
            return True

        # REVIEW → DECISION_READY: Owner and Admin only
        if current == CaseLifecycleStatus.REVIEW and new == CaseLifecycleStatus.DECISION_READY:
            return role in (Role.OWNER, Role.ADMIN)

        # DECISION_READY → EXPORTED: Owner, Admin, Reviewer
        if current == CaseLifecycleStatus.DECISION_READY and new == CaseLifecycleStatus.EXPORTED:
            return role in (Role.OWNER, Role.ADMIN, Role.REVIEWER)

        # EXPORTED → ARCHIVED: Owner and Admin only
        if current == CaseLifecycleStatus.EXPORTED and new == CaseLifecycleStatus.ARCHIVED:
            return role in (Role.OWNER, Role.ADMIN)

        # Any → DRAFT (reopen): Owner and Admin only
        if new == CaseLifecycleStatus.DRAFT:
            return role in (Role.OWNER, Role.ADMIN)

        return False
