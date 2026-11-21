# ADR 0062 — Verificação de CNPJ e vínculo automático do responsável

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`,
  `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `backend/app/api/v1/organizations.py`,
  `backend/app/modules/organizations/cnpj.py`,
  `backend/app/modules/organizations/verification.py`,
  `backend/app/modules/organizations/models.py`,
  `backend/migrations/versions/6f1a2b3c4d5e_organization_cnpj_verification.py`.

## Contexto

O painel permitia criar organização e quadra apenas com um nome. Um CNPJ
arbitrário podia ser informado depois como chave Pix de repasse, e nada provava
que a empresa existia, estava ativa ou pertencia ao responsável pelo cadastro.
Isso abria espaço para estabelecimentos fictícios, uso de CNPJ de terceiros e
publicação de quadras sem vínculo empresarial verificável.

A decisão do dono (2026-11-20/21) é exigir CNPJ válido e **ATIVO** para a
organização cadastrar quadras, com vínculo automático ao responsável, sem
procuração nem revisão manual nesta fase.

## Decisão

### 1. Identidade empresarial na organização

`organizations` passa a guardar:

| Campo | Conteúdo |
| --- | --- |
| `cnpj` | 14 dígitos, normalizado e único |
| `cnpj_status` | situação cadastral devolvida pela Receita (`ATIVA`, `BAIXADA`, …) |
| `cnpj_verified_at` | instante da última aprovação |
| `cnpj_next_check_at` | instante da próxima reverificação |
| `cnpj_snapshot` | JSONB com razão social, endereço, CNAE e QSA mascarado |
| `verification_status` | `pending`, `verified` ou `invalid` |

A organização da plataforma (`is_platform = true`) é isenta: as quadras
públicas são operadas pelo próprio JOGA e não representam um fornecedor.

### 2. Consulta externa

A consulta usa a BrasilAPI `GET /cnpj/v1/{cnpj}` com:

- timeout curto (`JOGA_CNPJ_TIMEOUT_SECONDS`, padrão 5 s);
- no máximo duas tentativas (`JOGA_CNPJ_LOOKUP_ATTEMPTS`);
- cache em memória de curta duração (`JOGA_CNPJ_CACHE_TTL_SECONDS`, padrão
  300 s);
- URL configurável por `JOGA_CNPJ_API_BASE_URL`.

Nenhum dado pessoal é registrado em log. O snapshot persistido contém o CPF dos
sócios apenas na forma mascarada devolvida pela fonte (por exemplo
`***682847**`), nunca o CPF completo.

### 3. Validações automáticas

1. **Dígitos verificadores** do CNPJ (`cnpj_invalid`).
2. **Situação cadastral ATIVA** (`cnpj_inactive`); baixada, suspensa ou inapta
   são recusadas.
3. **CNAE compatível** (`cnpj_cnae_incompatible`). A lista fechada aceita a
   atividade principal ou uma secundária entre:
   - `8591100` — Ensino de esportes;
   - `9311500` — Gestão de instalações de esportes;
   - `9312300` — Clubes sociais, esportivos e similares;
   - `9313100` — Atividades de condicionamento físico;
   - `9319101` — Produção e promoção de eventos esportivos;
   - `9319199` — Outras atividades esportivas;
   - `9329899` — Outras atividades de recreação e lazer.
4. **Endereço da quadra** (`cnpj_address_mismatch`). O município/UF precisam
   coincidir com o endereço do CNPJ. Quando o município não é informado, o
   prefixo de cinco dígitos do CEP é usado como proxy determinístico de raio,
   porque a BrasilAPI não devolve coordenadas.
5. **Responsável no QSA** (`cnpj_owner_mismatch`). O CPF informado no cadastro
   é comparado, em memória, com a máscara do QSA; o nome do perfil precisa
   coincidir com o sócio cujo CPF bateu. O CPF completo nunca é persistido na
   organização nem enviado à auditoria.
6. **Falha fechada** (`cnpj_lookup_unavailable`): provedor indisponível,
   resposta inválida ou tempo esgotado impedem a aprovação. O painel recebe
   mensagem estável e pode tentar novamente.

`POST /api/v1/organizations` passa a exigir `cnpj` e `cpf`. A resposta inclui
`cnpj`, `cnpj_status`, `verification_status`, `cnpj_verified_at` e
`cnpj_next_check_at`; o CPF nunca é ecoado.

Organizações existentes entram na migração como `pending` e podem se
regularizar por `POST /api/v1/organizations/{id}/verification` com o mesmo
corpo `{cnpj, cpf}`. O endpoint exige `ORGANIZATION_UPDATE`; depois de aprovado,
o CNPJ não pode ser trocado (`409 cnpj_change_not_allowed`) e a organização da
plataforma não é verificável (`409 organization_not_verifiable`).

### 4. Vínculo automático

O usuário autenticado que cria a organização é vinculado como `OWNER`. A prova
do vínculo é o CPF do responsável presente no QSA, com nome compatível. Se o
perfil ainda não tiver CPF, o CPF validado é cifrado e gravado no perfil com a
mesma AES-256-GCM já usada pelo domínio de perfil (ADR 0049 §9.3). Se o perfil
já tiver CPF diferente do informado, o cadastro é recusado.

O destino de repasse também fica amarrado ao CNPJ verificado: para uma
organização com `cnpj` preenchido, `PUT /organizations/{id}/payout` recusa
`legal_document` diferente (a plataforma continua isenta).

### 5. Bloqueio de quadra e publicação

- Organização não verificada recebe `409 organization_not_verified` ao tentar
  criar quadra.
- Publicar (`is_public = true`) ou reativar quadra de organização não
  verificada também é bloqueado.
- A vitrine de quadras e a formação de reservas só consideram organizações
  `verified` ou a organização da plataforma.
- A organização que se torna inválida na reverificação tem todas as quadras
  despublicadas (`is_public = false`) e desativadas (`status = inactive`).

### 6. Reverificação a cada sete dias

`cnpj_next_check_at` nasce em `created_at + 7 dias` e avança para `now + 7
dias` após cada execução. O relógio é por organização, portanto o processo é
staggered e não faz varredura global.

O worker leve `python -m scripts.recheck_organization_cnpj --limit 20` processa
apenas organizações vencidas, em lote pequeno. Em cada execução:

- situação não ATIVA, CNAE incompatível, endereço divergente ou responsável
  fora do QSA → `verification_status = invalid` e despublicação;
- provedor indisponível → mantém o status atual, agenda nova tentativa em
  `JOGA_ORGANIZATION_CNPJ_RETRY_HOURS` (padrão 6 h) e registra auditoria;
- sucesso → atualiza snapshot, situação, `cnpj_verified_at` e a próxima data.

### 7. Auditoria

Cada tentativa relevante grava evento append-only:

- `organization.cnpj_verified` — aprovação com CNPJ mascarado, situação, CNAE
  compatível e CPF mascarado do responsável;
- `organization.cnpj_rejected` — recusa de cadastro, com resultado e motivo;
- `organization.cnpj_recheck_ok` — reverificação aprovada;
- `organization.cnpj_recheck_failed` — invalidação e quantidade de quadras
  despublicadas;
- `organization.cnpj_recheck_unavailable` — falha de provedor e nova tentativa.

Os eventos nunca contêm CPF completo, chave Pix ou segredo.

## Consequências

- Organizações existentes nascem `pending` na migração. A plataforma nasce
  `verified`. Organizações `pending` não criam novas quadras; quadras já
  existentes continuam visíveis apenas se a organização for `verified` ou da
  plataforma.
- O seed de demonstração cria um snapshot explícito `source = demo_seed`; ele
  não representa consulta real à Receita e não deve ser usado fora do demo.
- A lista de CNAEs é conservadora e exige nova decisão para incluir atividades
  como boliche, sinuca ou jogos eletrônicos.
- A consulta síncrona adiciona latência ao cadastro; cache e timeout curto
  limitam o impacto. Uma indisponibilidade do provedor bloqueia novos
  cadastros, por decisão explícita de falha fechada.

## Fora do escopo desta fase

- Procuração, contrato social, revisão manual ou aprovação por operador.
- Verificação de CPF do responsável diretamente na Receita (o QSA é a fonte).
- Geocodificação do endereço do CNPJ para comparar raio em quilômetros.
- Revalidação de todos os sócios ou de alterações contratuais em tempo real.
- Notificação ao responsável quando a organização é invalidada.
