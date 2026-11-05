# JOGA — início do desenvolvimento com Codex

Este guia complementar prepara o repositório para um desenvolvimento incremental. O ponto de entrada principal é `README.md`. O repositório já contém código do aplicativo e do backend a partir da Fase 2.

## 1. Repositório da V2

JOGA será desenvolvido do zero como projeto independente no repositório `kramirodev/Joga`. O projeto anterior está em um repositório independente e poderá ser consultado futuramente como referência conceitual, sem obrigação de reutilizar código, arquitetura, banco ou histórico.

## 2. Estrutura inicial

Copie o conteúdo deste pacote para a raiz do repositório escolhido. A estrutura esperada é:

```text
.
├── AGENTS.md
├── GOALS.md
├── PLANS.md
├── PROMPTS.md
├── README_INICIO.md
├── docs/
│   ├── JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md
│   ├── JOGA_DOCUMENTACAO_TECNICA.md
│   └── ADR/
├── harness/
│   ├── build-log.md
│   ├── build/
│   └── context/
└── .github/
```

O repositório `kramirodev/Joga` já está vinculado a este workspace. Nenhuma renomeação ou outra alteração remota foi necessária.

## 3. Primeiro pedido ao Codex

Não peça para ele construir o aplicativo inteiro. Primeiro solicite uma inspeção somente de leitura. Use o primeiro prompt de `PROMPTS.md`.

Quando o Codex terminar, confira se ele entendeu as decisões, se encontrou contradições e se separou corretamente as fases. Só então peça a execução da Fase 0.

## 4. Regra de ouro

- Uma fase aprovada por vez.
- Uma branch curta por entrega funcional.
- Uma mudança de domínio por PR sempre que possível.
- Testes antes da implementação quando aplicável.
- Revisar o diff antes de aceitar.
- Nunca permitir que o Codex faça push, deploy, altere credenciais ou execute comandos destrutivos sem autorização explícita.
- Não avançar automaticamente para a próxima fase.

## 5. Decisões ainda abertas

As decisões ainda pendentes e suas fases responsáveis estão listadas em `docs/JOGA_DOCUMENTACAO_TECNICA.md`, seção 26. Escolhas de mobile e passkeys devem ser comprovadas na Fase 1; serviços e parâmetros de domínio devem ser decididos na fase que os implementa.
