"""Services package — business logic layer."""

from backend.discovery.services.query_generator import (
    QueryGeneratorConfig,
    QueryStrategy,
    as_config,
    generate_queries,
)
from backend.discovery.services.candidate_collector import (
    CandidateCollector,
    CollectorConfig,
    collect_candidates,
)
from backend.discovery.services.search_orchestrator import (
    SearchOrchestrator,
    SearchOrchestratorConfig,
    build_orchestrator_config,
)

__all__ = [
    "QueryGeneratorConfig",
    "QueryStrategy",
    "CandidateCollector",
    "CollectorConfig",
    "SearchOrchestrator",
    "SearchOrchestratorConfig",
    "as_config",
    "build_orchestrator_config",
    "collect_candidates",
    "generate_queries",
]