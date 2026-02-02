"""
Approval workflow for risky fixes.

Ported from StreamTV with all approval states preserved.
"""

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any

from exstreamtv.ai_agent.fix_suggester import FixRiskLevel, FixSuggestion

if TYPE_CHECKING:
    from exstreamtv.ai_agent.learning import FixLearningDatabase

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Approval status."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Request for approval of a fix."""

    id: str
    fix_suggestion: FixSuggestion
    status: ApprovalStatus
    requested_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    approved_by: str | None = None
    rejected_by: str | None = None
    rejection_reason: str | None = None
    expires_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["status"] = self.status.value
        result["fix_suggestion"] = self.fix_suggestion.to_dict()
        result["requested_at"] = self.requested_at.isoformat()
        if self.approved_at:
            result["approved_at"] = self.approved_at.isoformat()
        if self.rejected_at:
            result["rejected_at"] = self.rejected_at.isoformat()
        if self.expires_at:
            result["expires_at"] = self.expires_at.isoformat()
        return result


class ApprovalManager:
    """Manage approval workflow for risky fixes."""

    def __init__(
        self,
        default_expiry_hours: int = 24,
        learning_db: "FixLearningDatabase | None" = None,
    ):
        """
        Initialize approval manager.

        Args:
            default_expiry_hours: Default expiry time for approval requests.
            learning_db: Learning database for checking proven safe fixes.
        """
        self.default_expiry_hours = default_expiry_hours
        self._learning_db = learning_db
        self._pending_requests: dict[str, ApprovalRequest] = {}
        self._approved_requests: dict[str, ApprovalRequest] = {}
        self._rejected_requests: dict[str, ApprovalRequest] = {}

    @property
    def learning_db(self) -> "FixLearningDatabase":
        """Get or create learning database."""
        if self._learning_db is None:
            from exstreamtv.ai_agent.learning import FixLearningDatabase
            self._learning_db = FixLearningDatabase()
        return self._learning_db

    def requires_approval(self, suggestion: FixSuggestion) -> bool:
        """
        Check if a fix requires approval.

        Args:
            suggestion: The fix suggestion.

        Returns:
            True if approval is required.
        """
        # Check if proven safe - no approval needed
        if self.learning_db.is_proven_safe(suggestion):
            logger.info(f"Fix {suggestion.id} is proven safe, no approval required")
            return False

        # Safe fixes don't require approval
        if suggestion.risk_level == FixRiskLevel.SAFE:
            return False

        return True

    def request_approval(
        self,
        suggestion: FixSuggestion,
        requested_by: str | None = None,
    ) -> ApprovalRequest:
        """
        Request approval for a fix.

        Args:
            suggestion: The fix suggestion.
            requested_by: Who requested the approval.

        Returns:
            ApprovalRequest.
        """
        request_id = f"approval_{suggestion.id}_{datetime.now().timestamp()}"
        expires_at = datetime.now() + timedelta(hours=self.default_expiry_hours)

        request = ApprovalRequest(
            id=request_id,
            fix_suggestion=suggestion,
            status=ApprovalStatus.PENDING,
            requested_at=datetime.now(),
            expires_at=expires_at,
        )

        self._pending_requests[request_id] = request

        logger.info(f"Approval requested for fix: {suggestion.title} (ID: {request_id})")

        return request

    def approve(self, request_id: str, approved_by: str | None = None) -> bool:
        """
        Approve an approval request.

        Args:
            request_id: The approval request ID.
            approved_by: Who approved the request.

        Returns:
            True if approved successfully.
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Approval request not found: {request_id}")
            return False

        request = self._pending_requests.pop(request_id)

        # Check if expired
        if request.expires_at and datetime.now() > request.expires_at:
            request.status = ApprovalStatus.EXPIRED
            logger.warning(f"Approval request expired: {request_id}")
            return False

        request.status = ApprovalStatus.APPROVED
        request.approved_at = datetime.now()
        request.approved_by = approved_by or "system"

        self._approved_requests[request_id] = request

        logger.info(
            f"Approval granted for fix: {request.fix_suggestion.title} "
            f"(ID: {request_id})"
        )

        return True

    def reject(
        self,
        request_id: str,
        reason: str | None = None,
        rejected_by: str | None = None,
    ) -> bool:
        """
        Reject an approval request.

        Args:
            request_id: The approval request ID.
            reason: Reason for rejection.
            rejected_by: Who rejected the request.

        Returns:
            True if rejected successfully.
        """
        if request_id not in self._pending_requests:
            logger.warning(f"Approval request not found: {request_id}")
            return False

        request = self._pending_requests.pop(request_id)

        request.status = ApprovalStatus.REJECTED
        request.rejected_at = datetime.now()
        request.rejection_reason = reason
        request.rejected_by = rejected_by or "system"

        self._rejected_requests[request_id] = request

        logger.info(
            f"Approval rejected for fix: {request.fix_suggestion.title} "
            f"(ID: {request_id})"
        )

        return True

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        now = datetime.now()
        expired_ids = []

        for request_id, request in self._pending_requests.items():
            if request.expires_at and now > request.expires_at:
                request.status = ApprovalStatus.EXPIRED
                expired_ids.append(request_id)

        for request_id in expired_ids:
            request = self._pending_requests.pop(request_id)
            self._rejected_requests[request_id] = request

        return list(self._pending_requests.values())

    def get_approval_request(self, request_id: str) -> ApprovalRequest | None:
        """Get an approval request by ID."""
        if request_id in self._pending_requests:
            return self._pending_requests[request_id]
        if request_id in self._approved_requests:
            return self._approved_requests[request_id]
        if request_id in self._rejected_requests:
            return self._rejected_requests[request_id]
        return None

    def get_all_requests(self) -> dict[str, list[ApprovalRequest]]:
        """Get all approval requests grouped by status."""
        return {
            "pending": self.get_pending_requests(),
            "approved": list(self._approved_requests.values()),
            "rejected": list(self._rejected_requests.values()),
        }
