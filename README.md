# JOGA

JOGA conecta jogadores para partidas esportivas presenciais, com descoberta por região, formação de partidas, resultados competitivos auditáveis, descoberta de espaços e reserva de quadras com crédito e pagamento avulso. É um projeto independente, desenvolvido do zero.

## Arquitetura em alto nível

- Aplicativos móveis Android e iOS em React Native com TypeScript.
- Painel web de gestão em React + TypeScript + Vite, consumindo a mesma API.
- Backend Python com FastAPI em monólito modular, com processos de worker separados.
- PostgreSQL com PostGIS como fonte oficial da verdade; Redis somente para funções auxiliares e efêmeras.
- Comunicação do aplicativo com o backend por contratos HTTP/WebSocket versionados.

As Fases 0–9 do núcleo esportivo estão implementadas no backend e no mobile. A Fase 10 está em hardening local (10A/10B concluídos); o piloto real depende de provedores, orçamento, infraestrutura, revisão LGPD e das correções de autenticação/pagamento. As Fases 11–17 têm implementação local parcial ou completa; parte da 13C–13E, da 14D.10–16, da 16 e da 17 está na branch de trabalho, ainda sem merge. A ADR 0049 é a decisão vigente sobre crédito em reais, ticket como unidade de exibição, preço em duas linhas, NFS-e e custódia B→C; a Fase 14E concentra essa transição e a 14D/15 ficam congeladas até ela. O Mercado Pago é o PSP do protótipo com jogadores reais (ADR 0048); Inter PJ e Pagar.me ficam para o futuro. Dinheiro real permanece bloqueado até os pareceres da ADR 0049. O comércio de produtos está fora do escopo (ADR 0022).

## Por onde começar

1. Leia [`AGENTS.md`](AGENTS.md), [`docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`](docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md), [`GOALS.md`](GOALS.md) e [`PLANS.md`](PLANS.md) para instruções, a visão de produto (referência máxima), objetivos e sequência normativa das fases.
2. Consulte [`docs/JOGA_DOCUMENTACAO_TECNICA.md`](docs/JOGA_DOCUMENTACAO_TECNICA.md) para arquitetura e contratos-alvo; decisões ainda abertas estão identificadas por fase.
3. Leia a [`ADR 0049`](docs/ADR/0049-modelo-tributario-da-intermediacao.md) antes de mexer em crédito, preço, pagamento ou custódia.
4. Siga [`docs/RUNBOOK.md`](docs/RUNBOOK.md) para subir backend, banco local, verificações, painel web e aplicativo Android.
5. Consulte [`docs/PENDENCIAS.md`](docs/PENDENCIAS.md) para bloqueios externos, dívidas técnicas e itens ainda abertos.
6. Use [`PROMPTS.md`](PROMPTS.md) para preparar uma tarefa e [`harness/build/`](harness/build/) para revisar o escopo de cada fase.
7. Consulte [`harness/build-log.md`](harness/build-log.md) para status e evidências observadas.
8. [`README_INICIO.md`](README_INICIO.md) continua como guia complementar para organizar o início do trabalho.

Repositório: [github.com/kramirodev/Joga](https://github.com/kramirodev/Joga).
