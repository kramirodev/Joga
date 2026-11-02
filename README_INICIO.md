# Esporte Vivo — início do desenvolvimento com Codex

Este pacote prepara o repositório para um desenvolvimento incremental. Ele não contém código do aplicativo nem do backend.

## 1. Proteja o projeto antigo

Não apague nem sobrescreva o repositório atual para começar a V2.

Escolha uma destas opções:

- **Preferida para uma reconstrução limpa:** crie um novo repositório `esporte-vivo-v2` e mantenha o atual como legado/arquivo de referência.
- **Alternativa:** crie uma branch `rebuild/v2` no repositório atual e não altere a branch `main` até a V2 estar estável.

Não copie código antigo automaticamente. Reaproveite somente arquivos e comportamentos que forem revisados e aprovados.

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
│   └── DOCUMENTACAO_TECNICA.md
├── harness/
│   ├── build-log.md
│   ├── build/
│   └── context/
└── .github/
```

Depois, inicialize o Git (se for um repositório novo), faça o primeiro commit apenas da documentação de governança e abra o projeto no Codex.

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

A documentação define a arquitetura-alvo, mas algumas escolhas precisam ser comprovadas antes de virarem dependências permanentes: estratégia Expo/React Native com módulos nativos, biblioteca de passkeys, provedor de SMS, provedor de mapas/geocodificação, domínio técnico e infraestrutura de produção. O Codex deve comparar opções e propor um pequeno protótipo antes de escolher.
