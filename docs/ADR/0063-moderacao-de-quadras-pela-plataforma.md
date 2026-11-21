# ADR 0063 — Moderação de quadras pela plataforma, sem exclusão

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Relaciona:** ADR 0055 (quadra pública gratuita), ADR 0052 (payout da quadra
  pública), `backend/app/api/v1/admin_venues.py`,
  `backend/app/modules/venues/admin_moderation.py`,
  `backend/app/modules/venues/discovery.py`,
  `backend/app/modules/bookings/service.py` e ADR 0062 (CNPJ, número reservado).
- **Numeração:** o número **0062** está reservado para a decisão de CNPJ; esta
  ADR ocupa o próximo número livre, **0063**. Nenhuma migração foi criada.

## Contexto

O administrador da plataforma já operava a vitrine pública da organização
`joga-publico` por `/api/v1/admin/venues`, mas a listagem e as escritas eram
escopadas à própria organização da plataforma. Quadras de organizações de
terceiros não apareciam, e o administrador não conseguia suspendê-las nem
corrigir um cadastro abusivo sem acesso de membro da organização dona.

O dono do produto decidiu que a plataforma precisa enxergar **todas** as quadras
do aplicativo e moderá-las por violação de regra, preservando reservas,
histórico e dados financeiros. Excluir uma quadra apagaria ou tornaria órfão
esse histórico e não é uma operação aceitável.

## Decisão

### 1. Listagem global

`GET /api/v1/admin/venues` passa a listar quadras de **qualquer organização**,
inclusive as de terceiros, usando a mesma capability de plataforma dos demais
endpoints `/admin/*` (`require_platform_admin`). Não basta ser membro da
organização dona.

Filtros e paginação:

| Parâmetro | Regra |
|---|---|
| `q` | busca textual em nome, cidade e endereço, sem distinguir maiúsculas |
| `status` | `active` ou `inactive`; outro valor responde 422 |
| `is_public` | `true`/`false` |
| `organization_id` | UUID da organização dona |
| `active` | atalho booleano para `status` |
| `page`, `page_size` | `page >= 1`, `1..50`, padrão 20 |

A resposta traz `total` do conjunto filtrado antes da página, `page`,
`page_size` e a página de `venues`. Cada item inclui a organização dona
(`organization_id`, `organization_name`, `organization_is_platform`,
`organization_status`), `status`, `is_public`, `spaces_count`,
`active_spaces_count`, `created_at` e `updated_at`.

`GET /api/v1/admin/venues/{venue_id}` e `GET /api/v1/admin/venues/{venue_id}/spaces`
também são globais para permitir a inspeção antes da moderação.

### 2. Poderes de moderação

- `POST /api/v1/admin/venues/{venue_id}/suspend` — coloca a quadra em
  `inactive`.
- `POST /api/v1/admin/venues/{venue_id}/reactivate` — devolve a quadra para
  `active`.
- `PATCH /api/v1/admin/venues/{venue_id}` — edita somente campos cadastrais
  seguros: `name`, `city`, `state`, `address_line`, `postal_code`, `latitude`,
  `longitude` e `is_public`. A proveniência de geocodificação pode ser
  atualizada junto da coordenada.

As ações de estado exigem `reason` de **3 a 500 caracteres**. Motivo em branco
responde `422 reason_required`; motivo ausente, curto ou longo responde 422 de
validação.

O estado de suspensão usa o campo existente `organization_venues.status`
(`active|inactive`), sem novo status e sem migração. O motivo e o evento de
auditoria distinguem uma suspensão de uma desativação comum.

### 3. Auditoria

Toda ação efetiva grava `audit_logs`, append-only, com ator, organização dona,
recurso, motivo e diff:

| Ação | Efeito auditado |
|---|---|
| `admin.venue.suspended` | `changes.status` de `active` para `inactive` |
| `admin.venue.reactivated` | `changes.status` de `inactive` para `active` |
| `admin.venue.updated` | `changes.{campo}` no formato `{from, to}` |

O evento inclui `ip_hash` quando a rota recebe a requisição HTTP. Repetir a ação
no mesmo estado é idempotente quanto ao estado e continua auditado; nada é
reescrito ou removido. Correções futuras devem ser novos eventos.

### 4. Efeito operacional

A suspensão tem efeito imediato porque a vitrine e a criação de reservas já
consultam o estado da quadra:

- `VenueDiscoveryService.list_venues` e `get_venue` exigem
  `OrganizationVenue.status == "active"`; a quadra suspensa sai da vitrine e o
  detalhe público responde 404.
- `BookingService.create` exige `venue.status == "active"`; novas reservas são
  recusadas com 422 `invalid_input`.
- Reservas existentes, espaços, agenda, preços, pagamentos e histórico
  permanecem intactos. A reativação devolve a quadra à vitrine e às novas
  reservas sem reconstruir dados.

### 5. O que fica fora

- Exclusão ou hard delete de quadra, espaço, agenda ou reserva.
- Alteração de preço, faixa, disponibilidade, bloqueio, agenda, reserva,
  pagamento, repasse ou histórico pela moderação global.
- Criação, edição de espaços ou gestão de agenda de quadras de terceiros por
  `/admin/venues`; essas rotas continuam restritas à vitrine da plataforma.
- Suspensão automática por denúncia; a decisão continua humana e auditada.
- Migração de banco ou novo campo de status.

## Contrato de erros

Formato estável `{"detail": {"code": ...}}`:

- `401` sem sessão; `403 forbidden` sem capability de plataforma.
- `404 venue_not_found` para quadra inexistente.
- `422 invalid_input` para campo inseguro/valor inválido e para reserva em
  quadra suspensa.
- `422 reason_required` para motivo em branco após normalização.
- `422` de validação para `status` de filtro desconhecido ou motivo fora de
  3–500.

## Consequências

- O painel deve usar a listagem global e exibir a organização dona, o status e
  o motivo das ações.
- O app não precisa de novo contrato: a quadra suspensa simplesmente deixa de
  aparecer e de aceitar reservas.
- A moderação não substitui a gestão da organização; ela é uma intervenção de
  plataforma com motivo, limitada a cadastro e estado.
- Sem migração, o banco continua compatível com versões anteriores.
