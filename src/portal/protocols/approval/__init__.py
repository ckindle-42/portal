"""
Approval Protocol - Universal Human-in-the-Loop
================================================

This protocol provides interface-agnostic human approval for
sensitive operations.

Instead of tightly coupling approval logic to interfaces (e.g., Telegram buttons),
this protocol allows:
1. Agent generates ApprovalRequest event
2. Any interface can subscribe and render it appropriately
3. Interface returns ApprovalDecision

Benefits:
- Interface-agnostic approval flow
- Consistent approval logic across all interfaces
- Easy to add new approval mechanisms
"""

from .protocol import (
    ApprovalRequest,
    ApprovalDecision,
    ApprovalStatus,
    ApprovalProtocol,
    create_approval_protocol
)

__all__ = [
    'ApprovalRequest',
    'ApprovalDecision',
    'ApprovalStatus',
    'ApprovalProtocol',
    'create_approval_protocol',
]
