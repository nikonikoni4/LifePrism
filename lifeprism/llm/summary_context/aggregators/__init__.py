"""
Summary Context Aggregators

负责内容聚合的模块集合
"""

from lifeprism.llm.summary_context.aggregators.activity_aggregator import build_activity_context
from lifeprism.llm.summary_context.aggregators.authored_aggregator import build_authored_context
from lifeprism.llm.summary_context.aggregators.coverage_aggregator import build_coverage_context
from lifeprism.llm.summary_context.aggregators.execution_aggregator import build_execution_context

__all__ = [
    "build_activity_context",
    "build_authored_context",
    "build_coverage_context",
    "build_execution_context",
]
