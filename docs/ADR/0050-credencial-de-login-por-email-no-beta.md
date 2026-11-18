# ADR 0050 — Credencial de login por e-mail e senha no beta fechado

- **Status:** Aprovado pelo dono do produto em 2026-11-17. Revisado em 2026-11-18.
- **Data:** 2026-11-17
- **Revisão 2 (2026-11-18):** o login deixa de ser por código. A credencial
  primária passa a ser **e-mail + senha**; o código de 6 dígitos fica restrito à
  verificação do e-mail no cadastro e à redefinição de senha. A versão anterior
  (código como método primário de login) está superada. O contrato
  `v2026-11-18` fica superado por `v2026-11-19`.
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0013 (sessões e tokens), ADR 0014 (WebAuthn), ADR 0015
  (recibo de verificação de telefone), ADR 0016 (troca de telefone),
  `AGENTS.md` §4, `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`,
  `docs/CONTRATO_RESERVAS_APP.md`.

## Contexto

O lançamento do JOGA tem duas fases comercialmente diferentes:

1. **Beta fechado (fase atual).** O aplicativo é distribuído manualmente
   (APK), não está publicado em loja e não tem usuário real nem conta legada.
   O cadastro é **autoatendido e aberto na API**; "beta fechado" descreve a
   distribuição, não um gate de convite, allowlist ou cadastro por admin.
2. **Lançamento oficial.** Ocorre junto com financeiro e tickets. Telefone
   verificado volta como credencial e contato obrigatório; e-mail passa a ser
   secundário (recuperação e notificação).

O telefone é hoje a única credencial de login e é tratado como contato
verificado pela ADR 0016 e como identificador de contato pelo `AGENTS.md` §4.
Exigir SMS real no beta criaria custo, dependência de provedor e atrito antes de
existir receita. O e-mail permite validar o fluxo completo de identidade,
sessões, passkeys e recuperação sem contratar SMS.

A identidade continua sendo uma só: UUID interno (`users.id`) com múltiplas
credenciais. Não existe "usuário de e-mail" e "usuário de telefone" separados.
A fase é representada por **dados e flags**, não por `if` espalhado pelo código.

## Decisão

### 1. Modelo de identidade e credenciais

- `users.id` (UUID) continua sendo a identidade. E-mail e telefone são
  credenciais/contatos vinculados ao mesmo usuário.
- Nova tabela `user_emails` é a **autoridade da credencial de e-mail**:
  `id`, `user_id`, `email_normalized` (trim, minúsculas, domínio em punycode,
  máximo 254), `verified_at`, `is_primary`, `released_at`, `created_at`.
  - Índice único parcial em `email_normalized` onde `released_at IS NULL`:
    um e-mail ativo pertence a uma única conta.
  - Índice único parcial de um `is_primary = true` por usuário ativo.
  - Nenhum código de verificação é gravado em claro.
- `users.email` permanece como está: campo legado do pagador, sem `unique`,
  sem normalização e **sem autoridade de login**. Nenhum fluxo de autenticação
  o consulta.
- Telefone permanece implementado, porém **dormente por flag**. Não é removido,
  não é migrado e não é reescrito.
- Nova tabela `user_passwords` é a **autoridade da senha**:
  `user_id` (único), `password_hash` (string PHC do Argon2id, com salt e
  parâmetros embutidos), `password_changed_at`, `compromised_at`,
  `created_at`. Nunca existe senha em claro, hash reversível ou pergunta de
  segurança. `users.email` continua sem autoridade de login.
- A senha é **opcional na conta, obrigatória para login por e-mail**: passkey
  pode autenticar uma conta sem senha definida, e a primeira definição de senha
  acontece no cadastro ou na redefinição.
- A tabela `phone_challenges` passa a ser o armazenamento genérico de desafios
  de curta duração. Ela recebe `subject_type` (`phone` ou `email`) e as
  finalidades `email_verification`, `email_change` e `password_reset`. A
  finalidade `email_login` é **aposentada**: o valor permanece no enum por
  compatibilidade de dados, mas nenhuma rota o emite nem o aceita para
  autenticar. O HMAC do
  código continua sendo o existente (`hash_otp`), com o segredo de identidade
  já usado pelo telefone. O e-mail é identificado por um HMAC com rótulo
  próprio (`email`), portanto um hash de e-mail nunca colide com um hash de
  telefone.
- A coluna `phone_challenges.phone_hash` guarda o HMAC do **sujeito** do
  desafio (telefone ou e-mail). O nome histórico é mantido para não quebrar
  dados, ORM ou contrato interno; o significado é documentado no modelo.

### 2. Fase 1 (beta): e-mail + senha, telefone opcional

- Login por **e-mail + senha** é o método primário. Não existe etapa de código
  no login.
- O código de 6 dígitos tem exatamente dois usos: verificar o e-mail no
  cadastro e autorizar a redefinição de senha. A rota de login por código é
  removida; desligá-la por flag não basta se a flag puder ser ligada de novo.
- Senha com Argon2id, mínimo de 10 e máximo de 128 caracteres, passphrase
  permitida, sem exigência de composição. Senhas comuns e iguais ao e-mail são
  recusadas.
- Cadastro por e-mail é autoatendido e aberto na API, sujeito a rate limit,
  limite diário por IP, bloqueio de domínios descartáveis e kill switch.
- Telefone deixa de ser obrigatório; permanece como contato opcional quando a
  flag de telefone estiver ligada. Com `JOGA_AUTH_PHONE_ENABLED=false`, as
  rotas de telefone respondem indisponível e o app não as oferece.
- Passkeys continuam sendo o método preferencial e funcionam sem telefone:
  registro após o primeiro login e autenticação por credencial descobrível ou
  por e-mail informado, sem enumerar contas.
- Financeiro e tickets continuam bloqueados; esta ADR não liga dinheiro real.

### 3. Fase 2 (lançamento): telefone obrigatório, e-mail secundário

A fase 2 é troca de flags e permissões, sem reescrever o domínio:

```dotenv
JOGA_AUTH_EMAIL_ENABLED=true
JOGA_AUTH_PHONE_ENABLED=true
JOGA_ALLOW_EMAIL_REGISTRATION=true
JOGA_ALLOW_PHONE_REGISTRATION=true
JOGA_PHONE_REQUIRED_FOR_BOOKING=true
JOGA_SIGNUP_MODE=open
```

- `JOGA_PHONE_REQUIRED_FOR_BOOKING=true` passa a exigir telefone verificado
  antes de criar reserva.
- O login por e-mail + senha continua aceito (e serve de recuperação), mas o
  telefone verificado volta a ser o contato obrigatório de cadastro e o
  critério de participação
  em reservas.
- Nenhuma migração destrutiva é necessária: as tabelas de e-mail e telefone
  coexistem desde a fase 1.

### 4. Flags e validação de boot

Flags de fase (todas explícitas e validadas no boot):

```dotenv
JOGA_AUTH_EMAIL_ENABLED=true
JOGA_AUTH_PHONE_ENABLED=false
JOGA_ALLOW_PHONE_REGISTRATION=false
JOGA_ALLOW_EMAIL_REGISTRATION=true
JOGA_PHONE_REQUIRED_FOR_BOOKING=false
JOGA_SIGNUP_MODE=open              # open|closed (kill switch)
```

Flags da camada de e-mail:

```dotenv
JOGA_EMAIL_PROVIDER=brevo|resend|none|fake
JOGA_EMAIL_API_KEY=<secret>
JOGA_EMAIL_FROM=<remetente verificado>
JOGA_EMAIL_FROM_NAME=JOGA
JOGA_EMAIL_REPLY_TO=<opcional>
JOGA_EMAIL_TIMEOUT_SECONDS=10
JOGA_EMAIL_DAILY_BUDGET=250
JOGA_EMAIL_CODE_TTL_SECONDS=600
JOGA_EMAIL_MAX_PER_ADDRESS_PER_HOUR=5
JOGA_EMAIL_MAX_PER_IP_PER_HOUR=50
JOGA_EMAIL_RESEND_COOLDOWN_SECONDS=60
JOGA_SIGNUP_MAX_PER_IP_PER_DAY=20
```

Regras de boot (falham, não degradam):

- Pelo menos uma credencial habilitada.
- `email_provider != none` exige `api_key`, `from` e `from_name`.
- `auth_email_enabled=true` exige provedor configurado ou `fake` em
  `local/test/development/ci`.
- `fake` é recusado fora de ambiente local/teste.
- `email_daily_budget > 0` e estritamente menor que a cota do plano
  (Brevo free = 300/dia; Resend = 3.000/dia).
- Telefone desabilitado não pode manter cadastro por telefone habilitado nem
  `phone_required_for_booking=true`.
- Fora de `local/test/development/ci`: `JOGA_DEV_FIXED_OTP` proibido e segredos
  com valor padrão recusados (regra já existente, agora estendida ao e-mail).
- Nenhum segredo tem valor padrão versionado.

Perfis documentados:

| Perfil | email | phone | phone_required | signup |
|---|---|---|---|---|
| beta | on (primário) | off (dormente) | false | open |
| lançamento | on (secundário) | on (obrigatório) | true | open |

**Limites no beta e CGNAT.** O limite por endereço (`5/h`) é independente do
limite por IP (`50/h`) e do cadastro por IP/dia (`20`). O beta é distribuído a
testadores que podem compartilhar o mesmo IP de operadora/Wi-Fi; limites por IP
mais baixos bloqueariam pessoas legítimas. A evolução para limite por
dispositivo está registrada em `docs/PENDENCIAS.md`.

### 5. Camada transacional de e-mail

- `EmailSender` é um protocolo com `BrevoSender`, `ResendSender` e
  `FakeSender`. Brevo é o padrão do beta (free, 300/dia, um remetente
  verificado, sem cartão). Resend é alternativa com domínio verificado.
- O envio é assíncrono pela Outbox existente. A request HTTP nunca espera o
  provedor.
- Tipos transacionais: `email_verification`, `password_reset`,
  `password_changed`, `email_change_confirm`, `email_change_notice`, `welcome`,
  `security_alert`, `account_deletion_notice`. O tipo `email_login` deixa de ser
  emitido.
- Templates fixos em PT-BR, texto + HTML simples, sem imagem externa, sem
  pixel de rastreamento, sem redirect de clique, sem link mágico, sem telefone,
  CPF, endereço, localização ou dado de pagamento.
- `email_deliveries` registra a entrega sem corpo, código ou endereço completo:
  guarda `email_hash`, provedor, status, tentativas e código de erro interno.
- Idempotência por `(user_id, kind, referência)`, materializada em uma chave
  única. Retry não duplica a entrega.
- Falha do provedor não altera a resposta pública. Bounce permanente marca a
  credencial como não entregável após N falhas e exige recuperação por outro
  meio (passkey ou suporte).
- Alerta operacional em 80% do orçamento diário; 100% bloqueia **novo envio**
  com erro operacional, sem transformar a resposta pública em enumeração de
  conta.
- A Outbox guarda temporariamente destinatário e código para permitir o envio
  assíncrono. Esse payload é transporte efêmero, não log de entrega; um script
  de limpeza remove eventos já despachados. O `email_deliveries` nunca contém
  código nem corpo.

### 6. Segurança de senha e do código por e-mail

**6.1 Senha**

1. Hash com **Argon2id** (`argon2-cffi`, versão fixada no `pyproject.toml` e no
   lock). Parâmetros: memória **64 MiB** (`memory_cost=65536`), **3 iterações**
   (`time_cost=3`), **paralelismo 4** (`parallelism=4`), hash de **32 bytes**;
   salt por usuário embutido na string PHC
   (`$argon2id$v=19$m=65536,t=3,p=4$...`). Proibido SHA-256, MD5, PBKDF2
   caseiro ou "hash + salt" manual.
2. Senha nunca aparece em log, resposta, auditoria, OpenAPI ou query string.
   O backend não registra corpo de `/auth/email/login` nem de `/me/password`.
3. Erro de login é sempre `401 invalid_credentials`, idêntico para e-mail
   inexistente, senha errada, senha não definida e conta suspensa. Para e-mail
   inexistente, o backend executa uma verificação descartável para igualar o
   tempo de resposta.
4. Login limitado por e-mail e por IP, com backoff e `Retry-After`. Falhas
   repetidas geram evento de segurança sem senha.
5. A conta só autentica por senha com e-mail `verified_at` preenchido,
   credencial ativa (`released_at IS NULL`), credencial entregável e conta
   ativa.
6. Redefinição exige código válido no e-mail, grava a nova senha, revoga
   **todas** as sessões, envia `password_changed` e invalida o desafio. Não
   reativa conta suspensa.
7. Troca autenticada exige senha atual, revoga as outras sessões e envia
   `password_changed`.
8. Passkey continua preferencial e não pede senha. Uma conta com passkey e sem
   senha continua válida; definir senha é opcional.

**6.2 Código por e-mail**

9. Código de 6 dígitos, uso único, TTL, máximo de tentativas, cooldown de
   reenvio e limites por endereço e por IP. Reutiliza `OtpPolicy`, a tabela de
   desafios e o rate limiting existente; não há segundo mecanismo concorrente.
10. Código nunca aparece em log, resposta HTTP, auditoria ou log de entrega.
11. Solicitação de código responde de forma idêntica para e-mail existente e
    inexistente, com trabalho comparável.
12. Comparação em tempo constante (`hmac.compare_digest`) e hash com o segredo
    de identidade existente.
13. Troca de e-mail exige sessão autenticada, código no endereço **novo**,
    aviso ao endereço **antigo**, cooldown de 24 h e revogação das outras
    sessões. O endereço antigo nunca mais autentica.
14. Nenhuma resposta, erro ou OpenAPI expõe e-mail de terceiro, hash ou lista de
    contas.
15. Domínios descartáveis configuráveis são bloqueados; IP é registrado apenas
    como hash nos eventos de segurança.
16. `JOGA_SIGNUP_MODE=closed` bloqueia cadastro público imediatamente, sem
    deploy.

### 7. Contrato HTTP

- `POST /api/v1/auth/email/code` — solicita código com `purpose`
  `registration` ou `password_reset` (resposta genérica `202`).
- `POST /api/v1/auth/email/verify` — valida código e devolve recibo de curta
  duração.
- `POST /api/v1/auth/email/register` — cria conta (recibo + e-mail + senha +
  perfil) e agenda `welcome`.
- `POST /api/v1/auth/email/login` — **e-mail + senha** → sessão (access +
  refresh rotativo). Não recebe `challenge_id` nem `code`.
- `POST /api/v1/auth/email/password/reset` — código verificado + nova senha;
  revoga todas as sessões.
- `POST /api/v1/me/password` — troca autenticada com senha atual.
- A rota de login por código (`/auth/email/login` com recibo) é **removida**
  nesta revisão; não há flag que a reative.
- `POST /api/v1/me/account/email/challenges` — sessão autenticada; envia
  código ao endereço novo.
- `PATCH /api/v1/me/account/email` — troca autenticada com código no endereço
  novo. `GET/PUT /me/email` continua sendo apenas o e-mail do pagador.
- `GET /api/v1/auth/emails` — lista apenas as credenciais do próprio usuário.
- `POST /api/v1/auth/web/email/registration` — recibo + e-mail + senha, sessão
  de painel (cookie HttpOnly + CSRF).
- `POST /api/v1/auth/web/email/login` — e-mail + senha, sessão de painel. O
  painel não depende de telefone no beta.

As rotas de telefone existentes permanecem e ficam sob flag. O contrato é
aditivo; a versão e o comportamento das flags estão em
`docs/CONTRATO_RESERVAS_APP.md`.

## O que fica adiado

- Exigência de telefone verificado para cadastro, login e reserva.
- SMS real, custo e antiabuso de SMS.
- OAuth social (Google/Apple).
- Financeiro, tickets, PSP, NFS-e, escrow e KYC.
- E-mail marketing, newsletter, campanha e rastreamento de abertura.
- Domínio próprio e autenticação SPF/DKIM/DMARC do remetente (o beta usa
  remetente verificado no provedor).

## O que continua valendo

- `AGENTS.md` §4: telefone verificado é identificador de contato, não prova de
  identidade civil nem de pessoa única. A ADR 0016 continua correta quanto ao
  significado do telefone; esta ADR apenas **adia a exigência**.
- ADR 0015: o recibo de verificação continua sendo o desafio consumido, com
  TTL curto e uso único. O mesmo mecanismo serve ao e-mail, com finalidades
  próprias.
- ADR 0013: access token opaco, refresh rotativo, revogação por família.
- ADR 0014: passkeys com desafio de uso único e TTL.
- Identidade única por UUID; nunca um usuário por credencial.
- Toda autorização é verificada no servidor, por recurso e operação.

## Impacto nas ADRs 0015 e 0016

- **ADR 0015** permanece válida. `phone_challenges` é generalizada para
  `subject_type = phone|email` e ganha finalidades de e-mail, mas o recibo
  continua sendo o desafio consumido, com `consumed_at`, `receipt_used_at` e
  TTL. Nenhum recibo de telefone muda de formato.
- **ADR 0016** permanece válida para o fluxo de telefone. A troca de e-mail
  segue a mesma lógica (sessão autenticada + código no novo contato + aviso ao
  antigo + revogação de sessões), com cooldown de 24 h próprio. No beta, a
  troca de telefone fica indisponível por flag; no lançamento, volta sem
  reescrita.
- `AGENTS.md` §4 não é revogado: telefone verificado continua sendo contato,
  não identidade civil. A fase 1 apenas não o exige.

## Risco aceito

- **E-mail descartável.** O beta aceita endereços de provedores descartáveis
  que não estejam na lista configurada. Mitigação: lista de domínios, limite
  por IP/dia, rate limit, verificação por código e Trust Factor futuro. O risco
  é aceito porque não há dinheiro real, tickets ou reputação competitiva em
  jogo no beta.
- **Sem telefone verificado.** Uma conta pode existir sem telefone. Isso reduz
  a barreira de entrada e a capacidade de contato humano. Mitigação: passkey
  como método preferencial, e-mail verificado e a possibilidade de exigir
  telefone na fase 2. Nenhuma regra competitiva ou financeira depende de
  telefone no beta.
- **Cota de 300/dia (Brevo free).** Um pico de cadastros pode esgotar a cota e
  impedir novos códigos. Mitigação: orçamento configurado abaixo da cota,
  alerta em 80%, bloqueio em 100%, retry controlado e monitoramento. O beta é
  de distribuição manual e pequena.
- **Sem domínio próprio.** O remetente é verificado no provedor; reputação de
  domínio e DMARC ficam para o lançamento. Risco de entregabilidade é aceito
  e monitorado por bounce/falha.
- **Outbox carrega o código temporariamente.** Não há como o worker assíncrono
  recuperar o código a partir do HMAC. O payload é apagado após o despacho por
  rotina de limpeza; não é log, auditoria nem resposta.
- **Cadastro aberto.** `JOGA_SIGNUP_MODE=closed` é o kill switch. Não há
  allowlist de convite no beta por decisão de produto.
- **Senha reutilizada e credential stuffing.** Usuários reutilizam senhas e
  vazamentos de outros serviços viram tentativa de login aqui. Mitigação:
  Argon2id, erro genérico, rate limit por e-mail e por IP, backoff, recusa de
  senhas comuns e evento de segurança por falha repetida. Não há consulta a
  serviço externo de senha vazada nesta fase; fica como evolução.
- **Recuperação depende do e-mail.** Quem perde acesso ao e-mail perde a senha.
  Mitigação: passkey como caminho alternativo, aviso ao endereço antigo e
  suporte manual no beta. O worker de e-mail precisa estar ativo: sem ele, a
  redefinição de senha não completa.

## Alternativas consideradas

1. **Manter telefone no beta.** Rejeitado: custo de SMS, dependência de
   provedor e atrito antes de receita; o dono do produto decidiu e-mail.
2. **Criar um "usuário de e-mail" separado.** Rejeitado: viola identidade
   única, duplica sessões, passkeys e dados de perfil.
3. **Magic link de longa duração.** Rejeitado: link vira credencial portável,
   vaza em histórico de e-mail e é incompatível com o fluxo digitado no app.
4. **Guardar o e-mail como hash apenas.** Rejeitado: o provedor precisa do
   endereço em claro para entregar; a proteção fica no log de entrega (hash),
   na minimização e no acesso restrito.
5. **Criar um segundo sistema de fila/retry para e-mail.** Rejeitado: a Outbox
   e o dispatcher existentes já resolvem idempotência e retry.
6. **Provedor pago com domínio próprio no beta.** Adiado: Brevo free atende à
   distribuição manual; Resend fica como alternativa.
7. **Login por código em todo acesso (versão original desta ADR).** Rejeitado na
   revisão 2: o dono do produto decidiu e-mail + senha, e manter o código como
   login anularia a senha. O código fica restrito a cadastro e recuperação.
8. **Manter senha em texto ou hash rápido para simplificar.** Rejeitado: Argon2id
   é obrigatório; qualquer hash reversível ou rápido transforma um vazamento de
   banco em comprometimento de contas.

## Consequências

- O app mobile oferece **e-mail + senha** como login, esconde telefone quando
  `auth.phone.enabled=false` e usa o código apenas no cadastro e na recuperação.
- O painel web deixa de depender de telefone para autenticar e também usa
  e-mail + senha.
- Passkey continua como método preferencial depois do primeiro acesso.
- A fase 2 é uma mudança de flags, não uma reescrita.
- O runbook ganha operação de provedor, orçamento, fila e kill switch, e passa a
  incluir recuperação de senha dependente do worker de e-mail.
- A dívida de entregabilidade (domínio, SPF/DKIM/DMARC), a consulta a listas de
  senhas vazadas e a política de recuperação sem telefone ficam registradas em
  `docs/PENDENCIAS.md`.
- O contrato `docs/CONTRATO_RESERVAS_APP.md` §10 deve ser reversionado para
  `v2026-11-19`; a versão `v2026-11-18` fica superada.
