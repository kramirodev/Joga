"""Catálogo v2 (ADR 0079): planos mensais e passe de temporada separado.

P0 entrega apenas modelo, migração, seed, preço/validação e reembolso puros,
atrás da flag ``catalog_v2_enabled`` (desligada por padrão). Não há endpoints,
checkout, PSP de cartão nem recorrência nesta fase.
"""
