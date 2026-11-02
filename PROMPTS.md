# Prompts reutilizáveis para Codex — Esporte Vivo

Copie um prompt por vez. Substitua apenas o número/nome da fase ou tarefa. Não combine várias fases num único pedido.

## 1. Orientação inicial — somente leitura

```text
Leia AGENTS.md, GOALS.md, PLANS.md e docs/DOCUMENTACAO_TECNICA.md.
Inspecione o repositório atual em modo somente leitura.

Quero iniciar o Esporte Vivo do zero, sem perder nem copiar cegamente a implementação antiga.

Entregue:
1. Estrutura atual encontrada e arquivos relevantes.
2. Contradições entre o repositório e a documentação.
3. Riscos técnicos, especialmente passkeys Android/iOS, localização, identidade, concorrência e dados competitivos.
4. O que precisa ser decidido antes da implementação.
5. Um plano objetivo para a Fase 0, com arquivos exatos, comandos verificáveis e critérios de aceite.

Não edite arquivos. Não instale dependências. Não crie código, tabelas ou endpoints. Não altere branches, histórico Git, remotos, credenciais ou serviços externos. Não faça commit, push ou deploy. Pare após apresentar a análise.
```

## 2. Preparar uma fase — planejamento somente leitura

```text
Leia AGENTS.md, GOALS.md, PLANS.md, docs/DOCUMENTACAO_TECNICA.md, harness/build-log.md e os contextos/fases relevantes.
Prepare somente a Fase [NN — NOME].

Antes de propor a implementação, inspecione o estado real do repositório e identifique os comandos reais de lint, tipos, testes e build. Não invente comandos.

Entregue um plano com: objetivo, escopo, exclusões, dependências, arquivos prováveis, riscos, decisões pendentes, plano Red/Green/Refactor/Verify, testes, critérios de aceite observáveis e evidências exigidas. Separe claramente fatos observados de suposições.

Não altere nenhum arquivo e não comece a implementar. Pare para revisão humana.
```

## 3. Executar uma fase aprovada

```text
Execute exclusivamente a Fase [NN — NOME] conforme o arquivo aprovado em harness/build/.

Primeiro releia AGENTS.md, GOALS.md, PLANS.md, a documentação técnica, build-log e o arquivo da fase. Faça preflight somente de leitura: confirme estado do Git, arquivos afetados, dependências, testes existentes e riscos. Se houver mudanças não relacionadas no working tree, não as descarte; pare e relate.

Implemente em pequenos passos, usando Red/Green/Refactor/Verify. Não ultrapasse o escopo aprovado, não antecipe fases futuras e não adicione dependências sem justificar. Para cada regra crítica, inclua testes negativos e de falha. Atualize documentação e migrações quando necessário.

Ao concluir, execute os testes e verificações definidos. Revise o diff, procure segredos/dados pessoais expostos, problemas de autorização, concorrência e regressões. Registre evidências em harness/build-log.md e decisões materiais em harness/context/.

Não faça commit, push, merge, deploy, alteração de infraestrutura real nem chamadas que gerem custos sem autorização explícita. Pare ao terminar esta fase e apresente arquivos, comandos, resultados e pendências.
```

## 4. Revisão independente

```text
Faça uma revisão crítica das alterações atuais da Fase [NN]. Não modifique arquivos.

Leia as instruções e a fase aprovada. Inspecione o diff completo e procure prioritariamente:
- falhas de autorização/BOLA e mass assignment;
- exposição de telefone, tokens, localização ou evidências;
- replay, brute force, abuso de custos e recuperação insegura;
- transações incorretas, idempotência e condições de corrida;
- estados inválidos de partidas e aplicação duplicada de MMR;
- falhas de migração, rollback e compatibilidade;
- tratamento silencioso de erros e testes ausentes.

Para cada achado, informe severidade, arquivo/linha, cenário de exploração ou falha, impacto e correção sugerida. Diferencie vulnerabilidade demonstrada de risco hipotético. Não declare que o sistema é seguro apenas porque os testes passam.
```

## 5. Corrigir achados aprovados

```text
Corrija somente os achados [IDs] da revisão aprovada da Fase [NN].
Antes de editar, confirme que cada achado é reproduzível ou sustentado pelo código. Inclua primeiro o teste que falha, faça a correção mínima e rode as verificações relacionadas. Não faça refatorações laterais. Não corrija achados fora da lista sem pedir autorização. Ao final, mostre o diff e a evidência de cada correção.
```

## 6. Encerrar e preparar handoff

```text
Faça o encerramento da Fase [NN] sem iniciar a próxima.

Verifique cada critério de aceite do arquivo da fase. Só marque como concluído o que tiver evidência observada. Atualize harness/build-log.md com status, branch, resumo, comandos executados, resultados, links/identificadores de evidência e bloqueios. Registre em harness/context/ somente decisões e descobertas que afetem fases futuras. Não duplique a documentação canônica.

Confira `git diff --check`, liste arquivos alterados e confirme se há mudanças não relacionadas. Informe critérios não atendidos, riscos residuais e a próxima fase recomendada. Não faça commit, push ou deploy.
```

## 7. Investigar falha de teste sem alterar código

```text
Investigue a falha abaixo em modo somente leitura. Reproduza-a, se isso não exigir serviços externos ou dados reais. Não altere código nem testes.

[COLE A FALHA]

Identifique causa provável com evidência, arquivos envolvidos, menor teste de regressão possível e opções de correção. Informe se a falha é do código, ambiente, dependência ou teste. Pare antes de editar.
```
