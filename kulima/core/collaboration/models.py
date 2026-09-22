"""Collaboration models for comments, notes, and review requests (Phase 10).

These models implement the collaboration primitives that enable teams to work
together on assessments with comments, review requests, and approval workflows.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CommentAnchorType(str, Enum):
    """Types of entities that comments can be anchored to."""

    CASE = "case"
    DOCUMENT = "document"
    EVIDENCE_NODE = "evidence_node"
    SIGNAL = "signal"
    DECISION = "decision"


class Comment(BaseModel):
    """A comment or note on a case or its components.

    Comments can be anchored to different entities (case, document, evidence node,
    signal, decision) and support threaded discussions with editing and soft deletion.
    """

    id: str
    org_id: str
    case_id: str
    author_id: str
    body: str
    anchor_type: CommentAnchorType = CommentAnchorType.CASE
    anchor_id: str | None = None  # ID of the anchored entity
    parent_id: str | None = None  # For threaded replies
    created_at: datetime = Field(default_factory=datetime.utcnow)
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    mentions: list[str] = Field(default_factory=list)  # User IDs mentioned in the comment


class ReviewRequestKind(str, Enum):
    """Types of review/approval requests."""

    REVIEW = "review"  # Request for review
    APPROVAL = "approval"  # Request for final approval


class ReviewRequestStatus(str, Enum):
    """Lifecycle status of a review request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReviewRequest(BaseModel):
    """A request for review or approval of a case.

    Review requests move cases into the REVIEW state and assign a reviewer.
    Approval requests move cases from REVIEW to DECISION_READY when approved.
    """

    id: str
    case_id: str
    kind: ReviewRequestKind
    requested_by: str  # User ID of the requester
    requested_from: str  # User ID of the reviewer/approver
    status: ReviewRequestStatus = ReviewRequestStatus.PENDING
    resolution_note: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    due_at: datetime | None = None  # Optional deadline
