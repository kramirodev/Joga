"""Classificação dos ambientes de execução do backend.

Local/teste não são ambientes compartilhados; o demo é uma demonstração
privada com dinheiro simulado; qualquer outro valor é tratado como produção
(guardas estritas), inclusive ``staging``.
"""

from __future__ import annotations

LOCAL_ENVIRONMENTS = frozenset({"local", "test", "development", "ci"})
DEMO_ENVIRONMENTS = frozenset({"demo"})


def is_local(environment: str) -> bool:
    return environment.lower() in LOCAL_ENVIRONMENTS


def is_demo(environment: str) -> bool:
    return environment.lower() in DEMO_ENVIRONMENTS


def is_production(environment: str) -> bool:
    """Ambiente compartilhado com guardas de produção (demo e local excluídos)."""

    return not is_local(environment) and not is_demo(environment)
