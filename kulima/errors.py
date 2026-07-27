"""Pipeline stage errors for hackathon-visible failure diagnostics."""

from __future__ import annotations


class PipelineStageError(Exception):
    """Raised when a named intelligence stage fails."""

    def __init__(self, stage: str, message: str, cause: BaseException | None = None) -> None:
        self.stage = stage
        self.cause = cause
        detail = f"[{stage}] {message}"
        if cause is not None:
            detail = f"{detail} — {type(cause).__name__}: {cause}"
        super().__init__(detail)
        if cause is not None:
            self.__cause__ = cause


class EvidenceIntegrityError(Exception):
    """Raised when the Evidence Integrity Engine fails non-fatally.

    The pipeline catches this and continues with ``evidence_integrity = None``.
    It is never allowed to propagate to the top-level pipeline runner.
    """

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        self.cause = cause
        detail = f"[EvidenceIntegrity] {message}"
        if cause is not None:
            detail = f"{detail} — {type(cause).__name__}: {cause}"
        super().__init__(detail)
        if cause is not None:
            self.__cause__ = cause
