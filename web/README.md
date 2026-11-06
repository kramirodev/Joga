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
pnpm build
```

## Segurança

- O refresh token não é exposto ao JavaScript.
- O access token fica em memória e é renovado por `/api/v1/auth/web/refresh`.
- O cookie de CSRF é legível pelo JavaScript e enviado em `X-CSRF-Token`.
- Em produção, configure `JOGA_WEB_COOKIE_SECURE=true` e sirva o painel e a API
  no mesmo domínio/HTTPS.
- O painel nunca acessa o banco diretamente e não cria conta separada por papel.

## Limitações

- A sessão web usa cookies `SameSite=Strict`; o painel deve ser servido no mesmo
  site da API.
- Ainda não há testes automatizados de UI; a CI valida lint, formatação, tipos e
  build.
- A direção visual é uma base funcional (dark, Urban Sports/Soft Utility); assets,
  tipografia própria e testes com usuários continuam pendentes.
