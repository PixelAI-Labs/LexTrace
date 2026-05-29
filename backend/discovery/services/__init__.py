"""Services package — business logic layer."""

from backend.discovery.services.query_generator import (
    QueryGeneratorConfig,
    QueryStrategy,
    as_config,
    generate_queries,
)

__all__ = ["QueryGeneratorConfig", "QueryStrategy", "as_config", "generate_queries"]