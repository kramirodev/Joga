# Fase 14D.1 — Faixas de preço e teto da quadra

**Status:** implementado localmente em 2026-11-12. Este arquivo não registra aprovação de
preço final nem de política comercial.
**Branch:** `main`

## Fontes e contexto

- `PLANS.md` Fase 14D (fatia 1)
- ADR 0042 §3 (tabela 2D) e §9 (reajuste e pausa)
- `docs/ESPECIFICACAO_TEMPORADA_E_CATALOGO.md`
- Fase 12A (quadras, agenda e preços)

## Objetivo

Dar à agenda um **degrau de preço** em vez de um valor solto. Cada janela de
disponibilidade passa a apontar para a faixa da tabela 2D que cobre o seu preço, e o
estabelecimento não consegue mais se classificar numa faixa acima do próprio preço.

## Decisões desta fatia

| Tema | Decisão | Motivo |
|---|---|---|
| Resolução da faixa | **Por teto**, não por escolha: a menor faixa ativa cujo `max_price_cents` cobre o preço | Impede a quadra de se declarar "Premium" com preço de "Econômica" para aumentar a margem |
| Snapshot | `venue_availability.band_id` grava a faixa no momento da escrita | A reserva precisa saber com qual tabela foi precificada |
| Atributo visível | `venue_spaces.is_covered` | Alimenta o rótulo e o filtro de busca; não decide a faixa |
| Teto | Preço acima da última faixa (R$ 300) é rejeitado com `price_above_band` | Fora da tabela não há preço em ingressos |
| Reajuste | Vale para **reservas novas**; as já feitas mantêm preço e faixa | O preço é congelado na reserva, então não existe reserva afetada |
| Reajuste sem reserva | Permitido a qualquer momento | A tabela 2D é que é recalibrada por ciclo, não a quadra |

## Implementação

- `app/modules/pricing/models.py` — `PricingBand` (`code`, `label`, `max_price_cents`, `version`, `active`).
- `app/modules/pricing/service.py` — `resolve_band`, `list_active_bands`, `seed_default_bands`.
- `app/modules/venues/models.py` — `VenueSpace.is_covered`, `VenueAvailability.band_id`.
- `app/modules/venues/service.py` — resolução na criação e na edição; guarda de reserva futura;
  `PriceNotEligible` (`price_above_band`).
- `app/api/v1/pricing.py` — `GET /api/v1/pricing/bands`.
- Migração `a1c2e3f40517` — cria a tabela, semeia as seis faixas da versão 1, adiciona as
  colunas e preenche `band_id` das janelas existentes.

Faixas semeadas (versão 1):

| Código | Rótulo | Teto |
|---|---|---:|
| `economica_dia` | Econômica dia | R$ 120 |
| `economica_noite` | Econômica noite | R$ 150 |
| `padrao_dia` | Padrão dia | R$ 180 |
| `padrao_noite` | Padrão noite | R$ 220 |
| `coberta` | Coberta | R$ 260 |
| `premium` | Premium | R$ 300 |

## Testes

`tests/test_pricing_bands.py`:

- faixa resolvida pelo teto (R$ 120 → econômica; R$ 121 → próxima).
- preço acima da última faixa retorna `422 price_above_band`.
- reajuste é aceito e **só afeta reservas novas**: a reserva já criada mantém o `price_cents`.

Suíte completa, `ruff` e `mypy --strict` verdes em 2026-11-12.

## Limitações conhecidas

1. **Reajuste com reserva recorrente — resolvido.** O preço vale para reservas novas; as já feitas mantêm o valor congelado. Não há mais bloqueio.
2. **Preço por janela, não por quadra.** Uma quadra com preço de dia e de noite tem duas
   faixas. É coerente com a tabela, mas o painel precisa deixar isso explícito.
3. **A faixa não é renegociada.** Mudar de faixa hoje só acontece mudando o preço; a
   reclassificação contratual com aviso de 30 dias não existe ainda.
4. **Fora do teto não é elegível.** Quadra acima de R$ 300 não pode operar com ingresso até
   haver faixa nova — decisão de produto, não bug.

## Próxima fatia

**14D.2 — Fornecedor e chave de repasse:** CNPJ, chave Pix de titularidade, contrato com teto
por faixa e portão de elegibilidade.
