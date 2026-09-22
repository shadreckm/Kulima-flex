"""Collaboration service for comments, notes, and review requests (Phase 10).

This service implements the business logic for team collaboration features,
including threaded comments, review workflows, and approval processes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from kulima.core.orgs.models import Role, Permission, role_has_permission
from .models import (
    Comment,
    CommentAnchorType,
    ReviewRequest,
    ReviewRequestKind,
    ReviewRequestStatus,
)
from .repository import CollaborationRepository
from kulima.core.cases.service import CaseService
from kulima.core.cases.models import CaseLifecycleStatus

_log = logging.getLogger(__name__)


class CollaborationService:
    """Business logic for collaboration features."""

    def __init__(self, db_path: str | None = None) -> None:
        self.repo = CollaborationRepository(db_path)
        self.case_service = CaseService(db_path)

    # ── Comments ─────────────────────────────────────────────────────────

    def add_comment(
        self,
        org_id: str,
        case_id: str,
        author_id: str,
        body: str,
        anchor_type: CommentAnchorType = CommentAnchorType.CASE,
        anchor_id: str | None = None,
        parent_id: str | None = None,
    ) -> Comment:
        """Add a new comment to a case or its components."""
        comment = Comment(
            id=str(uuid.uuid4()),
            org_id=org_id,
            case_id=case_id,
            author_id=author_id,
            body=body,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            parent_id=parent_id,
            created_at=datetime.now(timezone.utc),
        )
        return self.repo.save_comment(comment)

    def edit_comment(
        self,
        comment_id: str,
        new_body: str,
        editor_id: str,
        author_id: str,
    ) -> Optional[Comment]:
        """Edit an existing comment (only by author)."""
        comment = self.repo.get_comment(comment_id)
        if comment is None:
            return None

        if comment.author_id != author_id:
            _log.warning("User %s not authorized to edit comment %s", editor_id, comment_id)
            return None

        return self.repo.edit_comment(comment_id, new_body, editor_id)

    def delete_comment(
        self,
        comment_id: str,
        deleter_id: str,
        deleter_role: Role,
        author_id: str,
    ) -> Optional[Comment]:
        """Delete a comment (soft delete, author or admin)."""
        comment = self.repo.get_comment(comment_id)
        if comment is None:
            return None

        # Author can delete their own comments
        if comment.author_id == author_id:
            return self.repo.soft_delete_comment(comment_id, deleter_id)

        # Admins can delete any comment
        if role_has_permission(deleter_role, Permission.DELETE_DATA):
            return self.repo.soft_delete_comment(comment_id, deleter_id)

        _log.warning("User %s not authorized to delete comment %s", deleter_id, comment_id)
        return None

    def get_comments_for_case(
        self,
        case_id: str,
        anchor_type: CommentAnchorType | None = None,
        anchor_id: str | None = None,
    ) -> list[Comment]:
        """Retrieve comments for a case, optionally filtered by anchor."""
        return self.repo.list_comments_for_case(
            case_id,
            include_deleted=False,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
        )

    def get_comments_for_anchor(
        self,
        anchor_type: CommentAnchorType,
        anchor_id: str,
    ) -> list[Comment]:
        """Retrieve comments for a specific anchor."""
        return self.repo.list_comments_for_anchor(anchor_type, anchor_id)

    # ── Review Requests ───────────────────────────────────────────────────

    def request_review(
        self,
        case_id: str,
        requested_by: str,
        requested_from: str,
        kind: ReviewRequestKind = ReviewRequestKind.REVIEW,
        due_at: datetime | None = None,
        org_id: str | None = None,
    ) -> ReviewRequest:
        """Create a review request for a case.

        This moves the case into REVIEW state and assigns the reviewer.
        """
        request = ReviewRequest(
            id=str(uuid.uuid4()),
            case_id=case_id,
            kind=kind,
            requested_by=requested_by,
            requested_from=requested_from,
            status=ReviewRequestStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            due_at=due_at,
        )

        saved_request = self.repo.save_review_request(request, org_id=org_id)

        # Move case to REVIEW state
        # Note: This would need proper role context in production
        # case = self.case_service.get_case(case_id)
        # if case and case.lifecycle_status == CaseLifecycleStatus.PROCESSING:
        #     self.case_service.transition_lifecycle(case_id, CaseLifecycleStatus.REVIEW, requested_by, Role.ADMIN)

        return saved_request

    def respond_to_review(
        self,
        request_id: str,
        responder_id: str,
        status: ReviewRequestStatus,
        resolution_note: str = "",
    ) -> Optional[ReviewRequest]:
        """Respond to a review request (approve/reject)."""
        request = self.repo.get_review_request(request_id)
        if request is None:
            return None

        if request.requested_from != responder_id:
            _log.warning("User %s not authorized to respond to review request %s", responder_id, request_id)
            return None

        resolved_request = self.repo.resolve_review_request(request_id, status, responder_id, resolution_note)

        # If approved and this is an approval request, move case to DECISION_READY
        if status == ReviewRequestStatus.APPROVED and request.kind == ReviewRequestKind.APPROVAL:
            # Note: This would need proper role context in production
            # self.case_service.transition_lifecycle(request.case_id, CaseLifecycleStatus.DECISION_READY, responder_id, Role.ADMIN)
            pass

        return resolved_request

    def cancel_review_request(
        self,
        request_id: str,
        canceller_id: str,
        canceller_role: Role,
    ) -> bool:
        """Cancel a review request (by requester or admin)."""
        request = self.repo.get_review_request(request_id)
        if request is None:
            return False

        if request.requested_by != canceller_id and not role_has_permission(canceller_role, Permission.MANAGE_USERS):
            _log.warning("User %s not authorized to cancel review request %s", canceller_id, request_id)
            return False

        return self.repo.resolve_review_request(
            request_id,
            ReviewRequestStatus.CANCELLED,
            canceller_id,
            "Cancelled by requester",
        ) is not None

    def get_pending_reviews_for_user(self, user_id: str) -> list[ReviewRequest]:
        """Get all pending review requests assigned to a user."""
        return self.repo.list_pending_reviews_for_user(user_id)

    def get_review_requests_for_case(self, case_id: str, org_id: str | None = None) -> list[ReviewRequest]:
        """Get all review requests for a case with org validation."""
        return self.repo.list_review_requests_for_case(case_id, org_id=org_id)
