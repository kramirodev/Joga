# JOGA y GESTÃO — painel web

Painel web responsivo para proprietários, administradores e operadores de
organizações/estabelecimentos. Consome a mesma API do aplicativo mobile.

## Escopo atual

- Login/registro por OTP com a mesma identidade do aplicativo.
- Refresh token em cookie `HttpOnly`; access token apenas em memória.
- CSRF de duplo envio para refresh/logout.
- Seleção de organização, membros/papéis, estabelecimentos e auditoria.
- Sem reservas, agenda, pagamentos, KYC, clãs, moderação ou publicidade.

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

Para testar o OTP sem provedor real, configure no backend:

```bash
export JOGA_DEV_FIXED_OTP=123456
```

O código fixo só deve ser usado em ambiente local/teste. Nunca configure isso em
produção.

## Verificações

```bash
pnpm lint
pnpm format:check
pnpm typecheck
pnpm test
pnpm build
```

`pnpm build` também valida a CSP gerada em `dist/index.html`.

## Segurança

- O refresh token não é exposto ao JavaScript.
- O access token fica em memória e é renovado por `/api/v1/auth/web/refresh`.
- O cookie de CSRF é legível pelo JavaScript e enviado em `X-CSRF-Token`.
- Em produção, configure `JOGA_WEB_COOKIE_SECURE=true` e sirva o painel e a API
  no mesmo domínio/HTTPS.
- O painel nunca acessa o banco diretamente e não cria conta separada por papel.
- O build injeta uma CSP estrita em `dist/index.html`, sem `unsafe-inline` nem
  `unsafe-eval`; `pnpm build` falha se a política não estiver presente.
- `frame-ancestors` não é aplicado por `<meta>` e precisa ser enviado pela
  hospedagem, junto com os demais cabeçalhos de segurança.

### Cabeçalhos de produção

O `<meta>` cobre o documento, mas a hospedagem deve enviar os cabeçalhos abaixo.
Exemplo para nginx:

```nginx
add_header Content-Security-Policy "default-src 'self'; base-uri 'none'; object-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self' data:; connect-src 'self'; form-action 'self'; frame-src 'none'; frame-ancestors 'none'; worker-src 'self'; manifest-src 'self'" always;
add_header X-Frame-Options "DENY" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "no-referrer" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=()" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

`vite preview` serve o build com a CSP do `<meta>`, mas não simula os
cabeçalhos da hospedagem.

## Observabilidade

- A API devolve `X-Request-ID` em todas as respostas.
- Quando uma chamada falha, o painel mostra a referência do erro para suporte.
- O painel tem um error boundary que evita tela branca e orienta recarregar.
- Não há envio de telemetria para serviço externo no escopo atual.

## Limitações

- A sessão web usa cookies `SameSite=Strict`; o painel deve ser servido no mesmo
  site da API.
- A direção visual é uma base funcional (dark, Urban Sports/Soft Utility); assets,
  tipografia própria e testes com usuários continuam pendentes.
- A CSP depende de a hospedagem enviar `frame-ancestors` e os demais cabeçalhos;
  o `<meta>` sozinho não cobre enquadramento.
