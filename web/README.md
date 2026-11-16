# JOGA y GESTÃO — painel web

Painel web responsivo para proprietários, administradores e operadores de
organizações/estabelecimentos. Consome a mesma API do aplicativo mobile.

## Escopo atual

- Login/registro por OTP com a mesma identidade do aplicativo.
- Refresh token em cookie `HttpOnly`; access token apenas em memória.
- CSRF de duplo envio para refresh/logout.
- Seleção de organização, membros/papéis, estabelecimentos e auditoria.
- Cadastro de destino de repasse (CNPJ e chave Pix) e status de prontidão.
- Quadras/espaços, modalidades, atributo de cobertura, agenda semanal, preços, bloqueios, expediente, fechamentos e fotos de quadra com revisão.
- Reservas: lista por organização, aceite/recusa, cancelamento, reembolso, presença e conclusão; T1/T2/T3 controlados pelo backend.
- Financeiro: resumo, repasses a receber, extrato e contestação.
- Sem PSP de produção, KYC contratual, classificador de IA e publicidade.

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

## Observabilidade

- A API devolve `X-Request-ID` em todas as respostas.
- Quando uma chamada falha, o painel mostra a referência do erro para suporte.
- O painel tem um error boundary que evita tela branca e orienta recarregar.
- Não há envio de telemetria para serviço externo no escopo atual.

## Limitações

- A sessão web usa cookies `SameSite=Strict`; o painel deve ser servido no mesmo
  site da API.
- A direção visual é um design system dark alinhado à marca JOGA (lime/coral), com
  tipografia de sistema. Assets próprios, fontes licenciadas e testes com usuários
  continuam pendentes.
- Datas e horários são formatados no fuso do navegador. A agenda do estabelecimento
  tem `timezone`, mas a exibição por fuso do local ainda não foi propagada em todas
  as telas; isso precisa ser resolvido junto da expansão para múltiplos fusos.
- A tela de moderação continua sendo uma ferramenta interna separada; não há central
  de notificações no painel.
- A CSP depende de a hospedagem enviar `frame-ancestors` e os demais cabeçalhos;
  o `<meta>` sozinho não cobre enquadramento.
