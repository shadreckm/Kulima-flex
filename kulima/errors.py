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
