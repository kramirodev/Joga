# JOGA

JOGA conecta jogadores para partidas esportivas presenciais, com descoberta por região, formação de partidas, resultados competitivos auditáveis, descoberta de espaços e reserva de quadras com pagamento individual. É um projeto independente, desenvolvido do zero.

## Arquitetura em alto nível

- Aplicativos móveis Android e iOS em React Native com TypeScript.
- Backend Python com FastAPI em monólito modular, com processos de worker separados.
- PostgreSQL com PostGIS como fonte oficial da verdade; Redis somente para funções auxiliares e efêmeras.
- Comunicação do aplicativo com o backend por contratos HTTP/WebSocket versionados.

As Fases 0–9 do núcleo esportivo estão implementadas no backend e no mobile, incluindo comunicação em tempo real (backend), chat, amigos, convites e painel mobile. Reservas pagas, pagamentos Pix, split, KYC de recebedor, interface financeira, clãs, moderação e publicidade **não estão implementados** e pertencem às Fases 11–19. O comércio de produtos está fora do escopo inicial (ADR 0022).

## Por onde começar

1. Leia [`AGENTS.md`](AGENTS.md), [`docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`](docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md), [`GOALS.md`](GOALS.md) e [`PLANS.md`](PLANS.md) para instruções, a visão de produto (referência máxima), objetivos e sequência normativa das fases.
2. Consulte [`docs/JOGA_DOCUMENTACAO_TECNICA.md`](docs/JOGA_DOCUMENTACAO_TECNICA.md) para arquitetura e contratos-alvo; decisões ainda abertas estão identificadas por fase.
3. Siga [`docs/RUNBOOK.md`](docs/RUNBOOK.md) para subir backend, banco local, verificações e aplicativo Android.
4. Use [`PROMPTS.md`](PROMPTS.md) para preparar uma tarefa e [`harness/build/`](harness/build/) para revisar o escopo de cada fase.
5. Consulte [`harness/build-log.md`](harness/build-log.md) para status e evidências observadas.
6. [`README_INICIO.md`](README_INICIO.md) continua como guia complementar para organizar o início do trabalho.

Repositório: [github.com/kramirodev/Joga](https://github.com/kramirodev/Joga).
