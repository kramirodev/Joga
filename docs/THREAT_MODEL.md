# Threat model — núcleo esportivo, reservas, pagamentos e painel de gestão

**Data:** 2026-11-24 (última atualização)
**Escopo:** identidade, perfil/descoberta, fila/matchmaking, partidas, resultados/disputas, rating, chat/social, Outbox, organizações, painel web, quadras, agenda, reservas, pagamentos, crédito, ledger, moderação, clãs, custódia B→C e infraestrutura do demo (Supabase, Cloudflare/Render), no backend, app mobile e painel.
**Fora do escopo:** produção comercial com dinheiro real, escrow contratado, publicidade e operação de NFS-e. Esses itens estão bloqueados pela ADR 0049 e pela Fase 19A.

## Ativos

- Contas, telefone, passkeys, sessões e dispositivos.
- Perfil esportivo, disponibilidade e região aproximada.
- Filas, lobbies, partidas, presença e histórico competitivo.
- Relatos, evidências, decisões de disputa e MMR.
- Mensagens de lobby, amizades, bloqueios e convites.
- Tokens de push, IDs de idempotência e eventos de Outbox.
- Organizações, vínculos, estabelecimentos, quadras, agenda e preços.
- Fotos de quadra, arquivos privados e metadados de revisão.
- Segredos de aplicação, credenciais de banco e logs.

## Atores

- Jogador autenticado legítimo.
- Jogador malicioso ou conta comprometida.
- Usuário não autenticado.
- Operador interno de revisão.
- Processo worker confiável.
- Provedor externo futuro (SMS, push, mapas).

## Fronteiras de confiança

1. App mobile → API HTTP/WebSocket: não confiável; toda entrada é validada.
2. Painel web → API HTTP: não confiável; cookie, CSRF e CSP reduzem abuso.
3. API → PostgreSQL/Redis: confiável, mas sujeita a concorrência e falhas.
4. Workers → PostgreSQL: confiáveis, mas idempotência e locks são obrigatórios.
5. Operador → CLI: confiável apenas se o ambiente e a lista de operadores estiverem protegidos.
6. API → storage de fotos: privado; o arquivo nunca é servido estaticamente.
7. Provedores externos → API: não confiáveis até validação criptográfica/autenticação.
8. Data API/PostgREST do Supabase → PostgreSQL: **não usada** pelo JOGA; se for
   habilitada, é não confiável e precisa de RLS, grants mínimos e ADR.
9. Cliente → Cloudflare/Render → Caddy: o IP de origem é dado de borda; só é
   aceito quando o peer imediato é privado e vem de `CF-Connecting-IP`.

## Ameaças e controles

| Ameaça | Exemplo | Controles atuais | Risco residual |
|---|---|---|---|
| Acesso a objeto de outro usuário (BOLA) | Ler partida, chat, perfil ou resultado alheio | autorização por recurso em todos os endpoints; testes negativos | cobertura manual de novos endpoints |
| Sequestro/replay de sessão | Reutilizar access/refresh token | hash de tokens, rotação, revogação, expiração curta, refresh automático no app | limite por dispositivo e reauth de operações sensíveis pendentes |
| Abuso de OTP/SMS | Enumerar telefones, reenviar códigos, testar códigos | HMAC de telefone, cooldown, limites por telefone/IP, uso único, sem OTP em logs | limite por dispositivo; enumeração na troca de telefone |
| Manipulação de resultado/rating | Votar várias vezes, forjar vencedor, editar MMR | elegíveis congelados, idempotência, quórum, revisão humana, rating no servidor, eventos append-only | conluio coordenado exige análise humana |
| Exposição de dados competitivos | Vazar MMR bruto por endpoint, ranking, perfil ou painel de rede; inferir nível individual a partir de célula de rede | MMR bruto não é retornado por nenhum endpoint; app mostra divisão/progresso; ranking e perfil alheio sem MMR; sem MMR de adversário antes da partida; rede só agregada e com amostra mínima | agregações pequenas ainda podem sugerir proximidade; calibrar amostra no piloto |
| Concorrência em partidas/rating | Dois workers fechando rodada ou aplicando rating | locks de linha, constraints únicas, transações, testes PostgreSQL | testes de carga ainda limitados |
| Abuso de chat | Flood, spam, assédio, mensagem gigante | autenticação, participação no lobby, limite de 2.000 caracteres, rate limit, sem mídia | moderação de conteúdo existe parcialmente; classificador local pendente |
| Convites abusivos | Spam de convites, convite a bloqueado | amizade obrigatória, bloqueio, limite por hora, unicidade, capacidade do lobby | denúncia de convite ainda não existe |
| WebSocket não autorizado | Assinar lobby alheio, sessão revogada | handshake autenticado, autorização por lobby, heartbeat/revalidação | entrega local; sem Redis/fan-out |
| Vazamento em logs | Tokens, telefone, query string, corpo | logs sem query string/corpo; request ID; revisão de eventos | revisão contínua necessária |
| Push token exposto | Token em resposta/log de outro usuário | token privado, único, revogável, sem listagem pública | provedor real ainda não configurado |
| Outbox duplicada/perdida | Evento entregue duas vezes ou parado | gravação transacional, status, idempotência do consumidor | dispatcher/push real pendente |
| Backup indisponível/corrompido | Perda de dados locais | `pg_dump`/`pg_restore` documentados e testados | produção exige storage externo, criptografia e RPO/RTO |
| Dependência vulnerável | Biblioteca com CVE | versões fixadas, CI, revisão de lockfile | auditoria automatizada de CVE ainda pendente |
| Enumeração de usuários | Buscar usuários/perfis livremente | sem endpoint global de busca; dados sociais limitados às relações | ranking expõe nome/divisão; revisar privacidade |
| Abuso de recursos | Payload grande, muitas conexões, carga | limites de tamanho, rate limiting parcial, timeouts | rate limit global e proteção de borda pendentes |
| Exposição do banco pela Data API do Supabase | `anon`/`authenticated` alcançarem tabelas de `public` via PostgREST, incluindo `TRUNCATE` e DML em `spatial_ref_sys` | RLS habilitada sem policies; `USAGE`/`CREATE` revogados de `PUBLIC`/`anon`/`authenticated`; `ALL` revogado em tabelas, sequences e funções do app; `security_invoker` nas views; default privileges revogadas; Data API/Storage/Auth sem uso e a desligar no dashboard; app usa só o papel owner com `BYPASSRLS` (ADR 0075) | desligar a Data API é ação manual fora do Git; `spatial_ref_sys` segue do `supabase_admin` |
| IP de borda compartilhado ou forjado | Todos os clientes caírem no mesmo balde de rate limit, ou `X-Forwarded-For`/`CF-Connecting-IP` forjados mudarem a chave | Caddy com `trusted_proxies static private_ranges`, `trusted_proxies_strict`, `client_ip_headers CF-Connecting-IP`, `header_up X-Forwarded-For {client_ip}` e remoção de `CF-Connecting-IP`/`True-Client-IP`; uvicorn confia só em `127.0.0.1` | se o host do Render aceitar tráfego fora do Cloudflare, validar se o header ainda pode ser forjado |
| Acesso cruzado entre organizações (BOLA) | Membro de uma organização lê ou altera membros, estabelecimentos, quadras, fotos, reservas ou financeiro de outra | vínculo obrigatório, capacidade por papel, consulta sempre escopada pela organização, 404 para não-membro e testes BOLA | ACL por quadra não existe; autorização é por organização |
| Upload de imagem maliciosa | Polyglot, malware, decompression bomb, EXIF com localização, arquivo acima do limite | validação real por Pillow, reencode JPEG, remoção de EXIF, limites de bytes/pixels/dimensões, storage privado e serving autorizado | antivírus dedicado e storage de produção pendentes |
| Abuso de revisão de foto | Organização aprovar conteúdo impróprio ou foto com pessoa | revisão por `OWNER`/`ADMIN`, motivo obrigatório na rejeição, auditoria, `OPERATOR` sem revisão | revisão independente e denúncia de foto pendentes |
| Dupla reserva | Dois aceites concorrentes para o mesmo espaço/intervalo | lock da linha do espaço, verificação transacional de holds/reservas, teste PostgreSQL concorrente | exclusão por intervalo no banco ainda não usada; cobertura por serviço; criação concorrente não testada |
| Timer adulterado ou reiniciado | Cliente tentar prorrogar T1/T2/T3 ou agir após o prazo | prazos no backend, timers independentes, rejeição após deadline, worker idempotente | T2 comercial implementado; validar feriados |
| Pagamento simulado exposto | Usar endpoint de simulação em produção | rota só permite ambiente local/teste/development/ci ou demo restrito ao participante ativo do booking (ADR 0053) | revisão de configuração de deploy necessária |
| Acesso indevido a reserva | Participante ou organização consultar reserva alheia | autorização por participante/organização em cada rota | testes contínuos a cada novo endpoint |
| Custódia no protótipo | Dinheiro real ficar na conta do JOGA sem segregação patrimonial | modelo B documentado, ledger e repasse em `starts_at + 2h`; CNPJ/contrato/revisão jurídica antes de dinheiro real | risco jurídico/regulatório se operar dinheiro real antes da 14E/19A |
| Ledger não integrado | Obrigação financeira ficar fora do ledger de dupla entrada | ledger novo existe com trigger; fluxos usam ledgers legados | P0: integrar na 14E |
| Preço/taxa não persistidos | Reserva não guardar valor do espaço, taxa e percentual | cálculo existe; persistência pendente | P0: 14E |
| Escrow/conta de terceiro | Uso indevido do saldo ou insolvência | modelo C exigido para escala; B no protótipo com risco declarado | contrato e fornecedor pendentes |
| CPF/NFS-e | Exposição de CPF ou documento fiscal ausente | placeholder; CPF a cifrar; NFS-e por reserva | 14E/19A |
| Troca de PSP sem abstração | Domínio acoplado ao Mercado Pago e difícil migrar no futuro | adaptador de PSP desacoplado; Mercado Pago é o PSP atual e Inter/Pagar.me ficam para o futuro (ADR 0048) | adaptador do Inter não é dependência do protótipo |
| Webhook de pagamento forjado/replay | Confirmar reserva sem pagamento real | assinatura HMAC, consulta server-to-server, `psp_webhook_events` idempotente; segredo e URL HTTPS obrigatórios fora do local | hash do corpo e rollback em falha pendentes |
| Divergência de valor/referência | PSP devolver valor diferente da cobrança | conferência de `amount_cents` e `external_reference` antes de aplicar status | conciliação periódica pertence à Fase 15 |
| Reembolso indevido/duplicado | Cancelar reserva e tentar estornar duas vezes ou reembolsar cobrança não paga | autorização por organização, idempotência por `payment_refunds`, ledger append-only e teste de repetição | reembolso parcial e compra de pacote não tratados |
| Reembolso após repasse | Estornar reserva já concluída/liberada | `VENUE_RELEASE` existe; `REVERSED` não é usado | P0: reverter/bloquear repasse |
| Cobrança dupla Pix + crédito | Pagar a vaga por Pix e depois quitá-la com crédito | — | P0: bloquear quitação se a vaga já estiver paga |
| Perda de crédito no T3 | Expirar reserva sem devolver crédito consumido | — | P0: devolver no T3 |
| Abuso de identidade visual | Foto de terceiro, ícone de perfil ofensivo, impersonação | sem fotos de pessoas; identidade de catálogo fechado validado pelo backend; nome/tag moderados; denúncia de perfil | catálogo e critérios de moderação ainda pendentes |
| Sequestro de sessão web | XSS, CSRF ou vazamento de refresh token | refresh em cookie `HttpOnly`/`SameSite=Strict`, access só em memória, CSRF de duplo envio em refresh/logout, CSP estrita no build e no header do Caddy, `frame-ancestors 'none'`, HSTS condicional, boot recusa `JOGA_WEB_COOKIE_SECURE=false` fora de local/teste | revisão dedicada de XSS pendente |

## Controles transversais

- Autorização no servidor em cada recurso e operação.
- IDs UUID não substituem autorização.
- Consultas de organização filtram pelo vínculo do usuário e pela organização proprietária do recurso.
- Validação e limites de entrada em todos os schemas.
- Queries parametrizadas via SQLAlchemy.
- Idempotência em operações críticas.
- Constraints e transações no PostgreSQL.
- Segredos fora do Git; `.env` não versionado.
- Logs sem PII, tokens, OTP, query string ou corpo.
- Health live/ready e request ID para operação.
- Erros do painel exibem o `X-Request-ID` como referência de suporte, sem detalhes internos.
- Painel com CSP estrita no build, testes de UI automatizados e error boundary.
- Retenção provisória e limpeza manual documentadas.
- Fotos de quadra entram apenas por fluxo autenticado de organização, com revisão e sem pessoas identificáveis.
- Fotos de quadra são validadas pelo conteúdo real, reencodadas em JPEG, têm EXIF removido e são servidas por endpoint autenticado com `no-store`.
- A revisão inicial de foto é restrita a `OWNER`/`ADMIN` e auditada; `OPERATOR` não revisa.
- Reservas são escopadas por participante ou organização; hold e confirmação usam lock transacional.
- T1/T2/T3 são registrados em timers independentes; o pagamento simulado é bloqueado fora de ambiente local/teste.
- O banco do demo não é exposto por Data API: `anon`/`authenticated` não têm `USAGE` no schema `public` nem grants nas tabelas do app; RLS fica ligada sem policies e o owner/BYPASSRLS atende a API (ADR 0075).
- O IP do cliente é resolvido na borda a partir de `CF-Connecting-IP` apenas quando o peer é privado; o `X-Forwarded-For` do cliente não é aceito como verdade e o uvicorn confia só no Caddy local.

## Decisão P3-10: cache e rate limit do catálogo público (2026-11-20)

**Registro canônico:** ADR 0054.

**Decisão:** manter `Cache-Control: no-store` em todas as respostas da API,
inclusive no catálogo público (`GET /api/v1/catalog/sports` e
`GET /api/v1/catalog/visual`). Não cachear na borda nesta fase.

**Motivos:**

- o `no-store` é um padrão de segurança global do middleware
  (`backend/app/core/observability.py`) e evita cache de resposta autenticada
  por engano;
- o Caddy padrão não tem cache HTTP; cachear exigiria CDN ou plugin, com custo,
  invalidação e risco de servir catálogo desatualizado;
- o catálogo é pequeno e mudado por ação administrativa, então o ganho não
  justifica a complexidade agora;
- uma regra ampla de cache em `/api/v1/catalog/*` poderia alcançar rotas
  privadas futuras.

**Código morto removido:** `backend/app/api/v1/discovery.py` definia
`Cache-Control: private, max-age=60` na foto de quadra. O middleware sobrescreve
qualquer header definido na rota com `no-store`; o header foi removido e o
efetivo continua sendo o do middleware. O teste
`test_photo_upload_review_serving_and_removal` cobre `no-store`.

**Rate limit:** não adicionar rate limit ao catálogo público. O módulo
`app/modules/ratelimit` usa `RateLimitCounter` com escrita/lock no PostgreSQL
por escopo/chave/janela; aplicá-lo a requisições anônimas do catálogo criaria
uma escrita em banco por leitura, pior que o abuso que tentaria conter. Risco
aceito: o catálogo é somente leitura, autenticado por sessão quando aplicável
(nas rotas de descoberta), e não altera estado. Se houver abuso, a mitigação
deve ser de borda (proxy/CDN com rate limit), não no app.

**Gatilhos de revisão:** adoção de CDN/edge cache; aumento de tráfego anônimo ou
custo de banco; necessidade de catálogo público sem autenticação; incidente de
abuso; ou mudança para cache com invalidação explícita. Nesse caso, criar
allowlist de paths públicos, TTL curto e teste de invalidação.

## Superfície pública intencional (2026-11-20)

Rotas sem sessão autenticada. Qualquer inclusão fora desta lista é regressão e
deve ser justificada em ADR e coberta por teste.

| Rota | Controle compensatório | Motivo |
|---|---|---|
| `GET /api/v1/health/live` e `/ready` | sem PII; `ready` não expõe detalhe de conexão | monitores e health check do Render não enviam credencial |
| `GET /api/v1/app-config` | somente versão/URL de atualização e flag de demo | app consulta antes do login para se atualizar (ADR 0051) |
| `GET /api/v1/legal/terms/current` | devolve apenas a versão aprovada vigente | termos precisam ser lidos antes do cadastro |
| `GET /api/v1/catalog/sports` e `/catalog/visual` | catálogo fechado, somente leitura, sem MMR ou dados de terceiros | identidade visual e esportes exibidos antes do login |
| `POST /api/v1/auth/*` (challenges, verify, registration, login, refresh, passkeys) | OTP/passkey, cooldown, rate limit, uso único, hash de token | criam ou renovam a própria sessão |
| `POST /api/v1/auth/email/*` (code, verify, register, login, password/reset) | OTP por e-mail, limite por endereço/IP, cooldown, orçamento diário | cadastro/login por e-mail (ADR 0050) |
| `POST /api/v1/auth/web/*` (registration, login, refresh, logout) | cookie `HttpOnly`/`SameSite=Strict`, CSRF de duplo envio, rate limit | sessão do painel web |
| `POST /api/v1/payments/mercadopago/webhook` | assinatura HMAC, consulta server-to-server, idempotência | callback do PSP (sem sessão do jogador) |
| `GET /.well-known/assetlinks.json` | somente o arquivo estático; nenhum diretório listado | Digital Asset Links do Android |

**Docs e schema desligados fora de local:** `docs_url`, `openapi_url` e
`redoc_url` do FastAPI são `None` quando `environment` não é local/teste
(`app.main` usa `is_local` de `app.core.environments`). Fora de local,
`/api/docs`, `/api/openapi.json` e `/redoc` respondem 404; em local/teste
continuam disponíveis. O objeto `app.openapi()` ainda pode ser gerado
internamente (testes e ferramentas), mas não é servido por HTTP.

**Headers de borda:** o `deploy/Caddyfile` envia `X-Content-Type-Options:
nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`,
`Permissions-Policy` (câmera, microfone e geolocalização desligados) e CSP com
`frame-ancestors 'none'` em todas as respostas. HSTS
(`max-age=31536000; includeSubDomains`) só é enviado quando
`X-Forwarded-Proto: https`, porque o TLS termina na borda do Render e o
processo recebe HTTP. O middleware da API mantém `no-store`, `nosniff` e
`no-referrer`, inclusive em respostas 500 não tratadas, que também carregam
`X-Request-ID` e corpo genérico `internal_error`.

## Endurecimento de 2026-11-24

Rodada de segurança disparada pelo alerta `rls_disabled_in_public` do Supabase e
pela revisão do IP real na borda. As correções estão em revisão; os registros
abaixo são os invariantes que devem permanecer verdadeiros depois do merge.

### Supabase, schema `public` e Data API

**Achado da auditoria read-only:** 120 tabelas em `public` sem RLS — 119 do app
(dono `postgres`) + `spatial_ref_sys` (PostGIS, dona `supabase_admin`).
`anon` e `authenticated` não tinham `SELECT`/`INSERT`/`UPDATE`/`DELETE` nas
tabelas do app, mas mantinham `TRUNCATE`; `anon` tinha DML completo em
`spatial_ref_sys`; `USAGE` no schema `public` para `PUBLIC`, `anon` e
`authenticated`; default privileges concedendo `ALL` a objetos novos.

**Modelo de ameaça:**

| Elemento | Descrição |
|---|---|
| Ativo | Dados do app em `public`, incluindo contas, reservas, ledger e auditoria; `spatial_ref_sys` do PostGIS |
| Ator | Qualquer portador da chave `anon` (pública por desenho) ou cliente da Data API; não requer sessão do JOGA |
| Vetor | PostgREST/Data API usando `anon`/`authenticated`, grant default ou `TRUNCATE`; DML direto em tabela de extensão |
| Impacto | Leitura, escrita ou destruição de dados sem passar pela API e pela autorização do JOGA |
| Controle | RLS habilitada sem policies; `USAGE`/`CREATE` revogados de `PUBLIC`/`anon`/`authenticated`; `ALL` revogado nas tabelas/sequences/funções do app; `security_invoker` nas views; default privileges revogadas; Data API/Storage/Auth sem uso e com desligamento recomendado |
| Residual | Desligar a Data API é ação de dashboard, fora do Git; `spatial_ref_sys` continua do `supabase_admin` e só é inalcançável pela falta de `USAGE` |

**Invariantes:** o app continua falando Postgres direto pelo Session pooler com
`postgres.<ref>` (`BYPASSRLS`); `anon`/`authenticated` não têm `USAGE` no schema
nem grants em objetos do app; toda tabela do app tem `relrowsecurity = true` sem
policy; toda view do app tem `security_invoker`; `service_role` não é usada pelo
JOGA e não é o caminho de operação.

**O que não fazer:** reconceder acesso a `anon`/`authenticated` para "consertar"
erro, criar policy `USING (true)`, habilitar Data API/PostgREST sem ADR, expor a
chave `anon` no app, desabilitar RLS em tabela ou alterar `spatial_ref_sys`/
`supabase_admin` à mão. A decisão completa está na ADR 0075; o procedimento
operacional e o reteste estão em `docs/RUNBOOK.md` §10 e `docs/DEPLOY_DEMO.md`
§4.

**Gatilhos:** novo alerta de RLS/grants; criação de tabela/view fora de migração;
adoção de Data API, PostgREST ou chave `anon`; troca do papel de conexão; upgrade
do Supabase que mude default privileges; incidente de acesso ou `TRUNCATE`.

### IP real atrás de Render + Cloudflare (SEC-002)

**Estado anterior:** o Caddy enxergava o peer interno do Render e não resolvia o
IP do cliente. Todos os clientes compartilhavam o mesmo balde de rate limit, e o
hash da chave não correspondia ao IP real. Além disso, cabeçalhos de
encaminhamento chegavam ao uvicorn sem sanitização.

**Controle em revisão:**

- bloco global do Caddy com `trusted_proxies static private_ranges` e
  `trusted_proxies_strict`;
- `client_ip_headers CF-Connecting-IP` como fonte do IP;
- proxy para o uvicorn com `header_up X-Forwarded-For {client_ip}`;
- remoção de `CF-Connecting-IP` e `True-Client-IP` antes do backend;
- uvicorn continua confiando apenas em `127.0.0.1` (`--forwarded-allow-ips
  127.0.0.1`), porque só o Caddy local fala com ele.

**Invariante:** o backend usa `request.client.host`, que passa a ser o IP
resolvido pelo Caddy; `X-Forwarded-For` recebido do cliente não é usado como
verdade. Se o peer imediato não for privado, o Caddy ignora os headers e o IP
volta a ser o do Render: nesse caso, **não** ampliar `trusted_proxies` para
faixas públicas; corrigir o ingresso (Cloudflare proxied, rede do Render) ou
aceitar o balde compartilhado de forma explícita.

**Residual:** se o host do Render continuar acessível fora do Cloudflare, um
cliente direto pode chegar com peer privado e forjar `CF-Connecting-IP`. Validar
o ingresso exclusivo pelo Cloudflare; até lá, o rate limit por IP é
best-effort contra abuso distribuído.

**Gatilhos:** mudança de CDN/proxy; host do Render exposto; rate limit global
ativado; incidente de força bruta ou abuso; alteração na cadeia de headers.

### Blueprint do Render e ambiente demo (SEC-004)

`render.yaml` passou a declarar `JOGA_ENVIRONMENT=demo` e `autoDeploy: false`
como política desejada, com o comentário de que o blueprint **não governa** o
serviço em execução. A fonte da verdade continua sendo o dashboard/API do
Render. O serviço atual **ainda está com `autoDeploy=yes`** (confirmado via API
em 2026-11-24), embora o handoff preveja deploy manual: o dashboard e o arquivo
estão divergentes e precisam ser alinhados/confirmados. O arquivo também não
contém todas as variáveis aplicadas no dashboard (por exemplo
`JOGA_TICKET_PURCHASE_ENABLED` e `JOGA_PLATFORM_ADMINS`); sincronizar o Blueprint
ou recriar o serviço exige conferir essas entradas antes, senão o demo volta a
um perfil incompleto.

**Gatilhos:** sincronização do Blueprint; recriação do serviço; troca de
`JOGA_ENVIRONMENT`; diferença entre dashboard e arquivo, inclusive
`autoDeploy`.

### Cookie `Secure` do painel (SEC-013)

A afirmação anterior de que `JOGA_WEB_COOKIE_SECURE` não tinha validação
obrigatória no boot está desatualizada. `backend/app/core/config.py` recusa o
boot fora de `local`/`teste` quando `JOGA_WEB_COOKIE_SECURE` é falso. O risco de
emitir cookie de refresh sem `Secure` por esquecimento de configuração está
fechado; resta a revisão dedicada de XSS.

## Riscos aceitos da auditoria de 2026-11-20

Auditoria de infraestrutura, segredos e dependências. Os três itens abaixo
foram identificados e **aceitos sem correção nesta fase**; nenhum bloqueia o
demo privado nem exige ação imediata.

### A. APK/AAB de demonstração assinado com certificado de debug

**Situação:** o APK/AAB usado no demo é assinado com o keystore de debug do
Android (`CN=Android Debug`, SHA-256 `FA:C6:…:3B:9C`), o mesmo declarado em
`web/public/.well-known/assetlinks.json` para a prova de passkey.

**Por que é aceito:** o artefato serve apenas à demonstração interna, instalado
por sideload. A chave de debug é compartilhada por qualquer instalação Android,
não tem custódia adequada (fica na máquina de build, sem cofre nem controle de
acesso) e não é aceita por loja.

**Limite explícito:** nunca publicar em Google Play/App Store nem distribuir
como build de produção com essa chave. A loja exige AAB assinado por chave de
upload própria, com custódia e rotação documentadas.

**Gatilhos de revisão:** primeira publicação em loja; primeiro build
distribuído fora do círculo de demonstração; troca do `package`
(`com.anonymous.joga`); renovação do `assetlinks.json`; suspeita de vazamento
do keystore de debug. Nesses casos: criar chave de release com custódia
(keystore fora do repositório, senha em cofre), assinar com ela e reemitir o
`assetlinks.json` com a nova impressão digital.

**Gatilho de usuários reais já disparado (2026-11-24):** o demo admite usuários
reais desde o SEC-001, aceito pelo dono. Isso **não** autoriza corrigir o
`assetlinks.json` com o certificado de debug nem distribuir o APK de debug. A
partir daqui, antes de qualquer distribuição fora do sideload interno, é
obrigatório: (1) gerar a chave de release com custódia; (2) fixar o `package`
definitivo; (3) reemitir o `assetlinks.json` com a impressão digital da chave de
release. O aceite atual cobre apenas o demo privado.

Registro operacional complementar: `docs/DEPLOY_DEMO.md`, seção 11.

### B. Advisories transitivos no app mobile

**Situação (verificado com `pnpm audit` em 2026-11-20):** `mobile/` tem 5
advisories, todos em dependências transitivas de ferramentas de build:
4 de `node-forge` (1 low, 3 moderate) via `expo → @expo/cli` e 1 moderate de
`minimatch` via `expo → @expo/fingerprint` e via `eslint-config-expo`. Nenhum
pacote vulnerável é empacotado no bundle do app; o uso é de CLI/ferramenta em
tempo de build.

**Verificação das demais frentes:** `backend/` sem vulnerabilidade conhecida
(`pip-audit -r requirements.lock`, exit 0) e `web/` com 1 advisory moderate de
`minimatch` via `eslint` — tooling de desenvolvimento, fora do bundle servido.
O relatório original da auditoria declarava `web` limpo; a diferença é esse
advisory de dev, registrado aqui para não ficar implícito.

**Por que é aceito:** corrigir exige subir `expo`/`@expo/cli` fora da versão
fixada do SDK (risco de quebrar o build nativo) ou forçar override de
transitivas sem teste em aparelho. O impacto é local ao processo de build e não
alcança o usuário final nem a API.

**Gatilhos de revisão:** atualização do SDK Expo; correção upstream disponível
dentro do SDK atual; advisory que passe a afetar código embarcado no app;
publicação em loja; incidente de supply chain no ecossistema Expo/npm. Nesses
casos: atualizar as dependências e revalidar `pnpm exec tsc --noEmit`, lint e
build nativo.

### C. URL real do demo no histórico do Git

**Situação:** a URL pública do Render existiu no commit `e47c750` e foi
removida em `5691752`. O histórico **não será reescrito** (repositório público;
force push e reescrita são proibidos). Hoje o host é derivável do próprio
repositório: `render.yaml` declara `name: joga-demo` e o Render publica
`https://<nome>.onrender.com`.

**Por que é aceito:** a URL não é segredo de autenticação. O SPA em `/` está
atrás de basic auth com hash bcrypt existente apenas no Render; `/api/*` exige
sessão, autorização por recurso e rate limit; o ambiente é demo privado com
dinheiro simulado. Reescrever histórico não remove o dado de forks e clones já
existentes.

**Gatilhos de revisão:** migração para domínio próprio; demo com dados de
usuários reais; aumento anormal de 401/tráfego no Caddy; incidente de acesso ao
painel; decisão de tornar o repositório privado (aí a reescrita passa a ser
avaliável). Nesses casos: rotacionar credenciais do demo, revisar o basic auth
e reavaliar a exposição da URL.

## Riscos residuais e bloqueios

- **Alto:** revisão LGPD/jurídica definitiva ainda não feita.
- **Alto:** backup/restore de produção, criptografia e storage externo não definidos.
- **Médio:** rate limiting global/borda e proteção contra abuso distribuído incompletos.
- **Médio:** Redis/fan-out multi-processo e múltiplas instâncias não implementados.
- **Médio:** push real e SMS dependem de provedor/credenciais.
- **Médio:** HSTS, CSP de header, `frame-ancestors` e `Permissions-Policy` saem do Caddy; `JOGA_WEB_COOKIE_SECURE=false` impede o boot fora de local/teste, então o cookie sem `Secure` está fechado.
- **Médio:** schema `public` do Supabase fechado por RLS/grants (ADR 0075); falta desligar Data API, Storage e Auth no dashboard e confirmar que o host do Render não é alcançável fora do Cloudflare.
- **Médio:** moderação de chat e denúncias têm backend/painel, mas o classificador local e a suspensão permanente não existem.
- **Médio:** catálogo de identidade por ícones e moderação de nome/ícone de perfil pendentes.
- **Médio:** revisão de foto de quadra ainda é feita pela própria organização; revisão independente e denúncia de foto pendentes.
- **Médio:** storage de fotos é local; provedor de produção, criptografia, backup e limpeza de órfãos não definidos.
- **Médio:** T2 comercial implementado; validar feriados, fusos e fechamentos.
- **Alto:** no protótipo, o pagamento usa o Mercado Pago com jogadores reais; dinheiro real exige CNPJ/MEI, contrato, 14E e revisão jurídica.
- **Alto:** o Mercado Pago centraliza o valor; repasse é ledger/manual no modelo B, sem split e sem escrow C.
- **Alto:** ledger de dupla entrada não integrado e taxa não persistida; correção na 14E.
- **Médio:** webhook do Mercado Pago ainda não foi validado com credenciais reais; testes usam HTTP simulado.
- **Médio:** e-mail do pagador é obrigatório na Orders API e o cadastro atual é por telefone.
- **Baixo:** catálogo público sem cache de borda e sem rate limit dedicado; risco aceito na decisão P3-10 (2026-11-20).
- **Baixo:** cobertura de UI mobile e testes em aparelho são manuais.

## Critérios para piloto

1. Restore local reproduzível e documentado.
2. Testes de carga local sem falhas críticas.
3. Nenhuma vulnerabilidade crítica/alta conhecida sem bloqueio explícito.
4. Limites de custo de SMS/mapas/infra definidos.
5. Responsável por incidentes e rollback definidos.
6. LGPD e retenção revisadas antes de dados reais.
