"""Erros do catálogo v2."""

from __future__ import annotations


class CatalogV2Error(Exception):
    """Erro base do catálogo v2."""


class CatalogV2Disabled(CatalogV2Error):
    """Flag ``catalog_v2_enabled`` desligada: operação não pode ser executada."""


class CatalogV2ProductNotFound(CatalogV2Error):
    """Produto inexistente, inativo ou de versão diferente."""


class CatalogV2PriceNotFound(CatalogV2Error):
    """Preço de tabela ausente para o meio/parcelamento pedido."""


class CatalogV2InvalidPayment(CatalogV2Error):
    """Meio ou parcelamento inválido para o produto."""
