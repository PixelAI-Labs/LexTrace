"""Query Generator Service."""

from copyguard.discovery.services.query_generator import (
    QueryGeneratorConfig,
    QueryStrategy,
    as_config,
    generate_queries,
)

__all__ = [
    "generate_queries",
    "as_config",
    "QueryGeneratorConfig",
    "QueryStrategy",
]