# JOGA y GESTÃO — painel web

Painel web responsivo para proprietários, administradores e operadores de
organizações/estabelecimentos. Consome a mesma API do aplicativo mobile.

## Escopo atual

- Login por e-mail + senha; o código de seis dígitos fica restrito ao cadastro e à recuperação de senha.
- Troca de senha autenticada no cabeçalho, com senha atual e nova; a senha não é armazenada no navegador.
- Refresh token em cookie `HttpOnly`; access token apenas em memória.
- CSRF de duplo envio para refresh/logout.
- Seleção de organização, membros/papéis, estabelecimentos e auditoria.
- Cadastro de destino de repasse (CNPJ e chave Pix) e status de prontidão.
- Quadras/espaços, modalidades, atributo de cobertura, agenda semanal, preços, bloqueios, expediente, fechamentos e fotos de quadra com revisão. O expediente é editado por `PATCH`, sem apagar e recriar a janela.
- Reservas: lista por organização, aceite/recusa, cancelamento, reembolso, presença e conclusão; T1/T2/T3 controlados pelo backend.
- Financeiro em reais sobre o ledger: resumo com comissão do JOGA separada do valor do fornecedor, repasses com composição e comprovante simulado, extrato do fornecedor, comissão por período, contestações com prazo e decisão, e detalhe financeiro por reserva com NFS-e placeholder.
- Moderação: fila paginada por `limit/offset` com filtro `IN_REVIEW`, decisão, recursos, operadores e **central de notificações internas**.
- Sem PSP de produção, escrow, KYC contratual, NFS-e operacional, classificador de IA e publicidade.

## Administração da plataforma

As rotas `/admin/users`, `/admin/sports` e `/admin/venues` só existem com a
capability `platform.admin` na sessão. A navegação é escondida, o portão
redireciona sem a capability e nenhuma chamada a `/admin/*` é feita antes da
verificação.

- **Usuários:** busca paginada por `q`, filtro por status, detalhe em drawer com
  CPF mascarado, auditoria `{events}` e ações de criar, alterar e-mail,
  redefinir senha, suspender, reativar e revogar sessões. Toda ação de escrita
  exige motivo. A criação usa `verify_email` explícito, desmarcado por padrão.
  O reset responde 204 e apenas envia o código para o e-mail da conta; o painel
  não exibe nem armazena senha temporária.
- **Esportes:** catálogo com seletor de ícone do catálogo visual, formatos
  estruturados, prévia, publicação/desativação com motivo e bloco de preço com
  as seis faixas, `k` sugerido, invariante e preço por jogador. Formatos já
  criados são somente leitura; `in_use` é exibido quando a API devolve. O modo
  de preço (`standard`/`contingency`) é explícito fora de 3x3, 5x5 e 6x6.
- **Quadras públicas:** lista paginada, formulário em etapas com CEP e
  coordenadas, espaços, disponibilidade semanal, expediente, prévia com selo
  “Pública” e ativação/desativação com motivo.
- **Compra de tickets:** desligada no escopo atual. O painel não renderiza ação
  de compra e trata `503 ticket_purchase_disabled`.
- **Contrato único:** o painel consome `verify_email`, `{events}`, `icon_key`,
  `period_count`, `players_per_team` e `band_code` + `mode`; não mantém aliases
  do contrato antigo.
- A fila e as dependências de backend estão em `ADMIN_TASK_QUEUE.md`.

## Desenvolvimento local

Requisitos:

- Node 24;
- pnpm 11.25.0;
- API rodando em `http://127.0.0.1:8000`;
- migrações aplicadas no backend (`alembic upgrade head`).

```bash
cd web
pnpm install --frozen-lockfile
pnpm dev
```

Abra `http://localhost:5173`. O Vite faz proxy de `/api` para a API local.

O alvo do proxy pode ser trocado para outro ambiente local sem editar o arquivo:

```bash
export JOGA_API_PROXY_TARGET=http://127.0.0.1:8001
pnpm dev
```

Em PowerShell: `$env:JOGA_API_PROXY_TARGET = "http://127.0.0.1:8001"`.

O cadastro de operador e a recuperação de senha usam código de e-mail (ADR 0050).
A resposta `202` apenas enfileira o envio; o worker entrega em lotes de 5 em 5
minutos. Com o backend local e `JOGA_EMAIL_PROVIDER=brevo` no `.env`, processe a
fila em outro terminal:

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.deliver_emails --loop --interval 30
```

Sem o worker, o `202` não entrega o código. O código expira em poucos minutos e
nunca deve ser compartilhado.

## Verificações

```bash
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
```

`pnpm build` também valida a CSP gerada em `dist/index.html`.

## Design system e formulários

- Tokens de cor, espaçamento, raio, sombra e movimento ficam em `src/styles.css`.
- Componentes reutilizáveis de campo, modal, confirmação, motivo, toast, abas e cabeçalho ficam em `src/components/ui/`.
- A navegação principal, a trilha de navegação e o estado ativo das seções usam URLs reais (`?tab=...`, `?space=...`), preservando voltar/avançar.
- Telefones usam seletor de país, máscara local e envio em E.164; o `+55` não precisa ser digitado.
- Limites, CNPJ, chave Pix, valores monetários, datas, horários e arquivos são validados no cliente com mensagens específicas antes do envio. O backend continua sendo a autoridade.
- Estados de carregamento, vazio, erro e sucesso são explícitos; ações destrutivas usam confirmação e motivo quando necessário.
- `prefers-reduced-motion` desliga animações e transições.

## Segurança

- O refresh token não é exposto ao JavaScript.
- O access token fica em memória e é renovado por `/api/v1/auth/web/refresh`.
- O cookie de CSRF é legível pelo JavaScript e enviado em `X-CSRF-Token`.
- Em produção, configure `JOGA_WEB_COOKIE_SECURE=true` e sirva o painel e a API
  no mesmo domínio/HTTPS.
- O painel nunca acessa o banco diretamente e não cria conta separada por papel.
- Fotos de quadra são exibidas por blob autenticado; a CSP permite `blob:` apenas em `img-src`.
- A revisão inicial de foto é feita por `OWNER`/`ADMIN`; `OPERATOR` envia e remove, mas não revisa.
- O build injeta uma CSP estrita em `dist/index.html`, sem `unsafe-inline` nem
  `unsafe-eval`; `pnpm build` falha se a política não estiver presente.
- `frame-ancestors` não é aplicado por `<meta>` e precisa ser enviado pela
  hospedagem, junto com os demais cabeçalhos de segurança.

### Cabeçalhos de produção

O `<meta>` cobre o documento, mas a hospedagem deve enviar os cabeçalhos abaixo.
Exemplo para nginx:

```nginx
add_header Content-Security-Policy "default-src 'self'; base-uri 'none'; object-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; form-action 'self'; frame-src 'none'; frame-ancestors 'none'; worker-src 'self'; manifest-src 'self'" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

`vite preview` serve o build com a CSP do `<meta>`, mas não simula os
cabeçalhos da hospedagem.

## Financeiro e repasses

- A substância financeira é o crédito em reais. O ticket é a unidade de exibição e
  consumo (R$ 3,10), não a unidade de conta.
- O valor do espaço pertence ao fornecedor e **nunca** é rotulado como receita do
  JOGA. A receita do JOGA é a comissão de intermediação (`joga_fee_cents`).
- `Cobrança total` (`charged_cents`) é o valor cobrado do jogador, não receita.
- No caminho por tickets, o valor do JOGA é o restante de
  `tickets × R$ 3,10 − valor do espaço`; o percentual é referência, não valor final.
- O repasse fica elegível em `starts_at + 2h`. Contestação aberta suspende o
  repasse. Reembolso após repasse aparece como `REVERSED` na agenda.
- `receipt_reference` é exibido como comprovante; no protótipo, `simulated:<release_id>`.
- NFS-e é exibida como placeholder (`pending_manual`), sem emissão operacional.
- A decisão de contestação é interna (`JOGA_REVIEW_OPERATORS`) e apenas exibida no
  painel do fornecedor; o estabelecimento não decide a própria contestação.

## Observabilidade

- A API devolve `X-Request-ID` em todas as respostas.
- Quando uma chamada falha, o painel mostra a referência do erro para suporte.
- O painel tem um error boundary que evita tela branca e orienta recarregar.
- Não há envio de telemetria para serviço externo no escopo atual.

## Limitações

- A sessão web usa cookies `SameSite=Strict`; o painel deve ser servido no mesmo
  site da API.
- Em 401/refresh inválido, o painel limpa os tokens e redireciona para `/login`
  preservando o destino em `state.from`; o login devolve ao caminho original.
- No beta, o login do painel é e-mail + senha; o código de e-mail só é usado no
  cadastro e na recuperação de senha. A senha tem de 10 a 128 caracteres, é
  validada no servidor e não é gravada em `localStorage`/`sessionStorage`.
- As rotas de telefone continuam no backend, mas o painel não as oferece enquanto
  `JOGA_AUTH_PHONE_ENABLED=false`. `PUT /me/email` não é credencial de login; é o
  e-mail do pagador.
- A direção visual é um design system dark alinhado à marca JOGA (lime/coral), com
  tipografia de sistema. Assets próprios, fontes licenciadas e testes com usuários
  continuam pendentes.
- Datas e horários são formatados no fuso do navegador. A agenda do estabelecimento
  tem `timezone`, mas a exibição por fuso do local ainda não foi propagada em todas
  as telas; isso precisa ser resolvido junto da expansão para múltiplos fusos.
- A tela de moderação continua sendo uma ferramenta interna separada; a **central de notificações internas está implementada** (`NotificationCenter`) e consome `/moderation/notifications`.
- A CSP depende de a hospedagem enviar `frame-ancestors` e os demais cabeçalhos;
  o `<meta>` sozinho não cobre enquadramento.
- O relatório de comissão pagina por `limit/offset` e usa o tamanho da página para
  inferir o fim do período; o contrato ainda não devolve `total`.
- Repasse, comprovante e NFS-e são simulados. Transferência real, MED/chargeback
  real, PSP de produção e emissão fiscal continuam fora do escopo do painel.
- A decisão de contestação não é oferecida ao fornecedor: ela é interna e exige
  `JOGA_REVIEW_OPERATORS`, conforme ADR 0049/contrato da Fase 15.
