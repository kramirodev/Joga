# ADR 0028 — Framework do painel web JOGA y GESTÃO

- **Status:** Aprovado pelo responsável em 2026-11-06, ao autorizar a continuidade da Fase 11 e a implementação do painel.
- **Data:** 2026-11-06
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` Fase 11; `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §4.2 e §4.3; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §1, §5.2, §13.1 e §20.2; `harness/build/phase-11-organizacoes-e-painel.md`.

## Contexto

A Fase 11 exige um painel web responsivo, autenticado, destinado a proprietários, gerentes e funcionários autorizados de estabelecimentos. O painel:

- não é site público nem vitrine;
- não substitui ERP;
- compartilha API, identidade, banco e infraestrutura com o aplicativo mobile;
- precisa funcionar no desktop e no navegador do celular;
- deve isolar organizações e registrar ações administrativas.

A documentação técnica admite React + TypeScript, mas exige que o framework final seja registrado em ADR. O aplicativo mobile já usa React Native + TypeScript, o que favorece reutilização de linguagem, tipos e conhecimento.

## Opções consideradas

### A. React + TypeScript + Vite (recomendada)

SPA estática consumindo a API versionada. Sem renderização no servidor, sem SEO e sem runtime Node em produção. Build estático pode ser servido por CDN ou pelo próprio backend/reverse proxy.

**Vantagens:** menor complexidade operacional; uma única API; deploy simples; bom encaixe para painel interno autenticado; ecossistema React maduro.

**Custos:** autenticação precisa ser desenhada com cuidado; exige proteção contra XSS e CSRF; não há SSR.

### B. Next.js

Framework React com SSR, rotas de servidor e possibilidade de BFF.

**Vantagens:** bom para sites públicos, SEO, renderização no servidor e cookies `HttpOnly` via rotas próprias.

**Custos:** adiciona runtime Node, mais superfície operacional e complexidade de deploy; SSR/SEO não são necessários para um painel autenticado.

### C. Templates server-side (Jinja/HTMX)

**Vantagens:** pouca dependência de JavaScript e sessão no servidor.

**Custos:** menor reaproveitamento do ecossistema React/TypeScript, interatividade mais limitada e divergência da direção técnica do projeto.

## Decisão proposta

1. Adotar **React + TypeScript + Vite** para o painel, em `web/`.
2. O painel será uma SPA autenticada, sem site público e sem SSR.
3. O roteamento será declarado no cliente; a autorização real permanece no backend, em cada endpoint.
4. A autenticação do painel será implementada na 11B com cookie `HttpOnly` same-origin e proteção CSRF, evitando guardar refresh token em `localStorage`. O access token não deve ser persistido em armazenamento acessível a JavaScript.
5. Em desenvolvimento, o Vite fará proxy para a API local. Em produção, o build estático será servido no mesmo domínio da API ou atrás do mesmo reverse proxy.
6. Nenhuma dependência de UI, gráficos ou estado será fixada nesta ADR; cada uma exige necessidade concreta e justificativa no plano da 11B.
7. O painel não acessa banco diretamente, não recebe segredo de banco e não cria conta separada por papel.

## Consequências

- A Fase 11B pode começar após a confirmação desta ADR.
- O backend precisará expor um fluxo de sessão web com cookies `HttpOnly`, `Secure` em produção, `SameSite` adequado e CSRF, reutilizando a identidade e os tokens existentes.
- Será necessário definir política de CSP, origem permitida, expiração e logout do painel.
- O painel será testado em desktop e no navegador do celular, com estados de carregamento, erro, vazio e falta de permissão.
- Se o produto exigir SEO, página pública de estabelecimento ou renderização no servidor no futuro, esta decisão deve ser revista em nova ADR.
- Nenhum provedor externo, deploy ou custo é autorizado por esta ADR.

## Critérios para aprovação

- Confirmar que o painel é interno e não precisa de SSR/SEO.
- Confirmar a preferência por simplicidade operacional (Vite) ou por BFF/SSR (Next.js).
- Confirmar que a autenticação web será cookie `HttpOnly` + CSRF na 11B.
