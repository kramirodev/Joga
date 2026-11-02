# JOGA

JOGA conecta jogadores para partidas esportivas presenciais, com descoberta por região, formação de partidas e resultados competitivos auditáveis. É um projeto independente, desenvolvido do zero.

## Arquitetura em alto nível

- Aplicativos móveis Android e iOS em React Native com TypeScript.
- Backend Python com FastAPI em monólito modular, com processos de worker separados.
- PostgreSQL com PostGIS como fonte oficial da verdade; Redis somente para funções auxiliares e efêmeras.
- Comunicação do aplicativo com o backend por contratos HTTP/WebSocket versionados.

Esta fase contém apenas documentação e governança. Não há ainda aplicativo, API, banco ou infraestrutura implementados.

## Por onde começar

1. Leia [`AGENTS.md`](AGENTS.md), [`GOALS.md`](GOALS.md) e [`PLANS.md`](PLANS.md) para instruções, objetivos e sequência normativa das fases.
2. Consulte [`docs/DOCUMENTACAO_TECNICA.md`](docs/DOCUMENTACAO_TECNICA.md) para arquitetura e contratos-alvo; decisões ainda abertas estão identificadas por fase.
3. Use [`PROMPTS.md`](PROMPTS.md) para preparar uma tarefa e [`harness/build/`](harness/build/) para revisar o escopo de cada fase.
4. Consulte [`harness/build-log.md`](harness/build-log.md) para status e evidências observadas.
5. [`README_INICIO.md`](README_INICIO.md) continua como guia complementar para organizar o início do trabalho.

Repositório: [github.com/kramirodev/Joga](https://github.com/kramirodev/Joga).
