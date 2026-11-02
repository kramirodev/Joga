# Fase 00 — Repositório e governança

**Status:** Complete
**Branch:** `main` (checkout ligado ao repositório aprovado)

## Fontes e contexto

- `AGENTS.md`
- `GOALS.md`
- `PLANS.md` (fonte normativa das fases)
- `PROMPTS.md`
- `docs/JOGA_DOCUMENTACAO_TECNICA.md` (sucessora de `docs/DOCUMENTACAO_TECNICA.md`)
- `docs/ADR/0001-repositorio-v2-e-roadmap.md`
- `docs/ADR/0002-nome-joga-e-repositorio-vinculado.md`
- `docs/ADR/0003-independencia-entre-projetos.md`
- `docs/ADR/0004-nome-do-produto-joga.md`
- `docs/ADR/0005-repositorio-joga.md`
- `harness/build-log.md`

## Objetivo

Preparar a documentação e a governança do JOGA, a ser desenvolvido do zero como projeto independente no repositório `kramirodev/Joga`.

## Escopo

- Apresentar o produto, arquitetura e navegação documental em `README.md`.
- Manter `README_INICIO.md` como guia complementar.
- Fazer `PLANS.md` prevalecer sobre resumos de roadmap na documentação técnica.
- Registrar decisões aprovadas em ADRs.
- Mapear decisões técnicas pendentes para a fase responsável.
- Preparar esta ficha e registrar fatos em `harness/build-log.md`.

## Fora do escopo

- Criar ou configurar o repositório no GitHub, abrir PR, commit ou executar outra ação remota.
- Auditar, preservar operacionalmente, verificar, migrar ou importar conteúdo do projeto anterior.
- Reutilizar código, arquitetura, banco de dados ou histórico do projeto anterior.
- Comprar, registrar, hospedar ou configurar domínio/DNS.
- Implementar funcionalidades ou estrutura de aplicação.
- Instalar dependências, configurar Docker/CI funcional, criar banco, tabelas ou endpoints.
- Iniciar a Fase 1 ou qualquer fase posterior.

## Pré-requisitos e dependências

- Aprovação explícita do plano da Fase 0: recebida.
- Destino exclusivo aprovado: `kramirodev/Joga`; vínculo confirmado localmente e por consulta somente de leitura ao GitHub.
- Não há dependência operacional com o repositório anterior.

## Arquivos envolvidos

- Alterados: `AGENTS.md`, `GOALS.md`, `PLANS.md`, `PROMPTS.md`, `README.md`, `README_INICIO.md`, `docs/DOCUMENTACAO_TECNICA.md`, ADRs anteriores para marcar supersessão, `harness/build-log.md`.
- Criados: `docs/ADR/0003-independencia-entre-projetos.md`, `docs/ADR/0004-nome-do-produto-joga.md`, `docs/ADR/0005-repositorio-joga.md`, esta ficha.

## Riscos e decisões pendentes

- O repositório remoto foi confirmado como `kramirodev/Joga`; o nome já estava correto, portanto não foi necessária escrita ou renomeação remota.
- O projeto anterior não é critério nem bloqueio operacional da Fase 0.
- Domínio técnico é necessário para associações de passkeys; validar requisitos na Fase 1. Registro e hospedagem não pertencem a esta fase.
- As demais decisões técnicas e suas fases estão listadas em `docs/JOGA_DOCUMENTACAO_TECNICA.md`, seção 26 (na época desta ficha, o arquivo se chamava `docs/DOCUMENTACAO_TECNICA.md` e a seção era a 18).

## Plano de verificação

- **Red:** os documentos continham nomes/destinos incompatíveis e exigências operacionais sobre o projeto anterior.
- **Green:** definir JOGA e `kramirodev/Joga` como nome e destino; remover dependências e critérios ligados ao projeto anterior.
- **Refactor:** revisar consistência da documentação, mantendo o projeto anterior apenas como referência conceitual opcional.
- **Verify:** executar `git diff --check`; buscar contradições de nome, destino e critérios; revisar diff e status local.

## Comandos reais de validação

- `git status --short --branch`
- `git diff --check`
- `rg -n "JOGA|projeto anterior|projeto antigo|preservação" PLANS.md README.md README_INICIO.md docs/DOCUMENTACAO_TECNICA.md harness/build/phase-00-repositorio-e-governanca.md`

Não há manifests, código de aplicação ou testes nesta árvore; não se aplicam comandos de build/teste de software nesta fase.

## Critérios de aceite

- [x] `README.md` apresenta JOGA, arquitetura em alto nível e navegação da documentação.
- [x] `README_INICIO.md` descreve `kramirodev/Joga` como destino exclusivo.
- [x] `PLANS.md` é a fonte normativa; as seções 16 e 21 da documentação técnica estão alinhadas.
- [x] ADR registra que a V2 é independente e não tem dependências operacionais com o projeto anterior.
- [x] Pendências técnicas identificam a fase responsável.
- [x] `git diff --check` passa.
- [x] O repositório `kramirodev/Joga` está provisionado e o workspace local aponta para ele.
- [x] Nenhuma credencial real foi adicionada nesta alteração documental (revisão do diff).

Nenhum critério de aceite exige auditar, preservar operacionalmente, migrar, importar ou verificar o projeto anterior.

## Evidências exigidas

- Resultado de `git diff --check` e revisão documental do diff.
- Evidência do remoto local e metadados consultados no GitHub em modo somente de leitura.
- Atualização factual em `harness/build-log.md`; marcar `Complete` somente após comprovar todos os critérios de aceite.

## Aprovação e condição de parada

A Fase 0 foi concluída com evidências documentais e do remoto vinculado. A Fase 1 pode iniciar conforme solicitação explícita do usuário.
