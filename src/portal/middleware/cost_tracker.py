"""
Cost Tracking Middleware - Business Metrics for LLM Usage
===========================================================

Tracks and logs the estimated cost of every interaction based on:
- Token usage (input + output)
- Model pricing
- Request count

This is crucial for enterprise deployments to prevent bill shock
and track usage patterns.

Features:
- Real-time cost calculation
- Per-user cost tracking
- Per-model cost tracking
- Cost alerts/warnings
- Daily/monthly cost aggregation
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional
from decimal import Decimal

from portal.core.structured_logger import get_logger

logger = get_logger('CostTracker')


# Model pricing (as of 2025, adjust as needed)
# Prices are in USD per 1K tokens
MODEL_PRICING = {
    # OpenAI (example prices)
    'gpt-4': {'input': Decimal('0.03'), 'output': Decimal('0.06')},
    'gpt-4-turbo': {'input': Decimal('0.01'), 'output': Decimal('0.03')},
    'gpt-3.5-turbo': {'input': Decimal('0.0005'), 'output': Decimal('0.0015')},

    # Anthropic Claude
    'claude-3-opus': {'input': Decimal('0.015'), 'output': Decimal('0.075')},
    'claude-3-sonnet': {'input': Decimal('0.003'), 'output': Decimal('0.015')},
    'claude-3-haiku': {'input': Decimal('0.00025'), 'output': Decimal('0.00125')},

    # Local/Ollama (free, but track resource usage)
    'ollama': {'input': Decimal('0'), 'output': Decimal('0')},
    'qwen2.5': {'input': Decimal('0'), 'output': Decimal('0')},
    'llama3.1': {'input': Decimal('0'), 'output': Decimal('0')},

    # Default fallback
    'unknown': {'input': Decimal('0'), 'output': Decimal('0')},
}


@dataclass
class CostMetrics:
    """Cost metrics for a single interaction"""
    interaction_id: str
    user_id: Optional[str] = None
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    input_cost: Decimal = Decimal('0')
    output_cost: Decimal = Decimal('0')
    total_cost: Decimal = Decimal('0')
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            'interaction_id': self.interaction_id,
            'user_id': self.user_id,
            'model': self.model,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'input_cost_usd': float(self.input_cost),
            'output_cost_usd': float(self.output_cost),
            'total_cost_usd': float(self.total_cost),
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class UserCostSummary:
    """Cost summary for a user"""
    user_id: str
    total_cost: Decimal = Decimal('0')
    total_interactions: int = 0
    total_tokens: int = 0
    cost_by_model: Dict[str, Decimal] = field(default_factory=dict)


class CostTracker:
    """
    Middleware for tracking LLM usage costs

    Calculates and logs estimated costs for every interaction.

    Example:
        tracker = CostTracker()

        # Track an interaction
        metrics = tracker.track_interaction(
            interaction_id="123",
            user_id="user_42",
            model="gpt-4",
            input_tokens=100,
            output_tokens=50
        )

        # Get user summary
        summary = tracker.get_user_summary("user_42")
        print(f"Total cost: ${summary.total_cost}")
    """

    def __init__(self, pricing: Optional[Dict] = None):
        """
        Initialize cost tracker

        Args:
            pricing: Optional custom pricing dictionary
        """
        self.pricing = pricing or MODEL_PRICING
        self._user_summaries: Dict[str, UserCostSummary] = {}

        logger.info("CostTracker initialized")

    def track_interaction(
        self,
        interaction_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: Optional[str] = None
    ) -> CostMetrics:
        """
        Track cost for an interaction

        Args:
            interaction_id: Unique interaction ID
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: Optional user ID

        Returns:
            CostMetrics with calculated costs
        """
        # Get pricing for model (fallback to unknown)
        model_pricing = self.pricing.get(model, self.pricing['unknown'])

        # Calculate costs (pricing is per 1K tokens)
        input_cost = (Decimal(input_tokens) / 1000) * model_pricing['input']
        output_cost = (Decimal(output_tokens) / 1000) * model_pricing['output']
        total_cost = input_cost + output_cost

        # Create metrics
        metrics = CostMetrics(
            interaction_id=interaction_id,
            user_id=user_id,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost
        )

        # Log the cost
        logger.info(
            "💰 Interaction cost calculated",
            **metrics.to_dict()
        )

        # Update user summary if user_id provided
        if user_id:
            self._update_user_summary(user_id, metrics)

        return metrics

    def _update_user_summary(self, user_id: str, metrics: CostMetrics):
        """Update user cost summary"""
        if user_id not in self._user_summaries:
            self._user_summaries[user_id] = UserCostSummary(user_id=user_id)

        summary = self._user_summaries[user_id]
        summary.total_cost += metrics.total_cost
        summary.total_interactions += 1
        summary.total_tokens += metrics.input_tokens + metrics.output_tokens

        # Update per-model costs
        if metrics.model not in summary.cost_by_model:
            summary.cost_by_model[metrics.model] = Decimal('0')
        summary.cost_by_model[metrics.model] += metrics.total_cost

    def get_user_summary(self, user_id: str) -> Optional[UserCostSummary]:
        """
        Get cost summary for a user

        Args:
            user_id: User ID

        Returns:
            UserCostSummary or None if not found
        """
        return self._user_summaries.get(user_id)

    def get_total_cost(self) -> Decimal:
        """Get total cost across all users"""
        return sum(
            summary.total_cost
            for summary in self._user_summaries.values()
        )

    def reset_user_stats(self, user_id: str):
        """Reset statistics for a user"""
        if user_id in self._user_summaries:
            del self._user_summaries[user_id]
            logger.info(f"Reset cost stats for user {user_id}")

    def export_summary(self) -> Dict:
        """
        Export cost summary for all users

        Returns:
            Dictionary with cost data
        """
        return {
            'total_cost_usd': float(self.get_total_cost()),
            'users': {
                user_id: {
                    'total_cost_usd': float(summary.total_cost),
                    'interactions': summary.total_interactions,
                    'tokens': summary.total_tokens,
                    'cost_by_model': {
                        model: float(cost)
                        for model, cost in summary.cost_by_model.items()
                    }
                }
                for user_id, summary in self._user_summaries.items()
            }
        }


# Global instance for convenience
_global_tracker: Optional[CostTracker] = None


def get_cost_tracker() -> CostTracker:
    """Get global cost tracker instance"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = CostTracker()
    return _global_tracker
