# ADR 0010 — Início da Fase 2 com pendências externas da Fase 1

- **Status:** Aprovado pelo responsável do produto em 2026-11-02.
- **Data:** 2026-11-02
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0009 (estratégia Expo), ficha da Fase 1 e `PLANS.md`.

## Contexto

A Fase 1 permanece `In progress` porque dois critérios dependem de condições externas: validação real de passkeys com domínio/RP e arquivos de associação publicados, e build/teste iOS em macOS/Xcode (ou build cloud autorizado). As duas condições exigem decisões e custos que ainda não foram autorizados.

O `PLANS.md` define a ordem das fases, mas não proíbe trabalho paralelo quando um bloqueio é externo e não afeta o escopo seguinte. A Fase 2 (fundação de engenharia) não depende de passkeys, iOS ou provedor de SMS: depende apenas de estrutura de repositório, backend mínimo, banco local, CI e instruções reproduzíveis.

## Decisão

1. Iniciar a Fase 2 em paralelo, na branch `feat/02-fundacao-engenharia`, sem encerrar a Fase 1.
2. Manter a Fase 1 como `In progress`, com as pendências externas registradas na ficha da fase e no `harness/build-log.md`.
3. Não declarar suporte multiplataforma completo e não marcar a Fase 1 como `Complete` enquanto os critérios de domínio/RP e iOS não forem executados ou formalmente aceitos como bloqueio pelo responsável.
4. Limitar a Fase 2 ao escopo de `PLANS.md`: estrutura, configuração, banco local, migração vazia, health checks, testes mínimos, lint/formatação/tipos, CI e instruções locais. Nenhuma funcionalidade de produto, tabela de domínio, autenticação real ou arquitetura distribuída.
5. Não misturar as duas fases no mesmo commit. A publicação da Fase 2 exige autorização específica.

## Justificativa

Manter o trabalho parado até um domínio ser contratado e um macOS estar disponível transfere para o ambiente externo o controle do cronograma e não reduz risco técnico. A fundação de engenharia é pré-requisito de todas as fases seguintes e pode ser validada com o que já existe: Android comprovado na Fase 1, PostgreSQL/PostGIS local e pipeline de verificação.

## Consequências

- Duas frentes documentais passam a coexistir: a Fase 1 continua com pendências explícitas e a Fase 2 tem ficha própria.
- A conclusão da Fase 2 não implica conclusão da Fase 1; o roadmap mantém as duas visões separadas.
- A Fase 3 (identidade e segurança) continua bloqueada até a fundação estar verificável, incluindo CI observado em execução.
- Qualquer decisão de domínio, conta Apple, build cloud ou provedor de SMS continua exigindo autorização específica e ADR própria quando alterar arquitetura, segurança ou contratos.

## Limitações registradas

- Nenhum domínio foi escolhido, registrado ou configurado.
- Nenhuma conta Apple, build iOS ou serviço pago foi utilizado.
- A CI foi escrita, mas ainda não foi observada em execução no GitHub; esse é o critério aberto da Fase 2.
