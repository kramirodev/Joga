# ADR 0072 — Tipo de esporte e busca no catálogo

- **Status:** Aprovado em 2026-11-23 (decisão do dono).
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `backend/app/modules/catalog/sports.py`;
  `backend/app/api/v1/catalog.py`; `backend/app/api/v1/admin.py`.

## Contexto

O catálogo de esportes cresceu e a lista plana deixou de ser navegável: não
havia busca por nome nem filtro por tipo. O app precisa encontrar o esporte em
poucos toques antes de escolher formato e modo.

## Decisões

1. **Quatro tipos fechados:** `collective`, `individual`, `racket` e `beach`.
   Nesta rodada cada esporte tem **um** tipo; modalidades híbridas usam o mais
   específico (beach tennis → `racket`; futevôlei/vôlei de areia → `beach`).
2. **Coluna no esporte:** `sports.category VARCHAR(20) NOT NULL DEFAULT
   'collective'` com CHECK dos quatro valores. O default cobre esportes criados
   pelo painel sem escolha; o admin corrige no PATCH.
3. **Busca pública:** `GET /catalog/sports?q=&category=`.
   - `q` opcional, 2–40, `ILIKE` em `name` e `slug`, com `escape_like`;
   - `category` opcional e fechada; inválida → 422;
   - sempre `active = true` e ao menos um formato ativo;
   - duas consultas fixas (esportes + formatos), sem N+1.
4. **Admin:** `POST` aceita `category` (default `collective`); `PATCH` aceita
   `category` opcional; `AdminSportView` expõe o campo; auditoria inclui a
   categoria.
5. **Sem índice de categoria:** quatro valores de baixa cardinalidade não
   justificam o custo; reavaliar se o catálogo chegar a milhares de linhas.

## Consequências

- Migração `c8d9e0f1a2b3` adiciona a coluna, o CHECK e faz o backfill por slug.
- O app mobile deve enviar `q`/`category` e renderizar `sports[].category`, sem
  filtrar localmente.
- O painel precisa de um select de categoria no cadastro/edição do esporte.
- Esportes novos sem categoria nascem `collective`; o admin deve revisar.
- Multi-categoria (ex.: beach tennis em `racket` + `beach`) exigiria tabela de
  junção e fica para uma rodada futura, se o produto pedir.
