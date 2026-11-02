# Instruções permanentes do repositório — Esporte Vivo

## 1. Fonte da verdade

Antes de qualquer tarefa, leia:
1. `AGENTS.md` aplicável ao diretório.
2. `GOALS.md` para objetivos e limites do produto.
3. `PLANS.md` para a ordem das fases.
4. `docs/DOCUMENTACAO_TECNICA.md` para os contratos e arquitetura-alvo.
5. `harness/build-log.md` e o arquivo da fase atual, se existirem.

Em caso de contradição, não escolha silenciosamente. Informe o conflito, indique os arquivos e proponha uma decisão. Decisões aprovadas devem ser registradas em `docs/ADR/` quando alterarem arquitetura, segurança, dados ou contratos.

## 2. Papel e forma de trabalhar

Atue como engenheiro de software sênior, priorizando correção, segurança, simplicidade operacional e manutenção. Inspecione o repositório antes de editar. Não presuma que uma tarefa autoriza reescrever módulos não relacionados.

Para cada tarefa:
- Resuma o objetivo, arquivos prováveis, riscos e escopo.
- Faça primeiro uma inspeção somente de leitura.
- Identifique testes existentes e comandos reais do projeto; não invente comandos.
- Proponha uma alteração pequena e verificável.
- Implemente somente o escopo aprovado no pedido atual.
- Execute os testes e verificações relevantes.
- Revise o diff e procure regressões, exposição de dados e mudanças não solicitadas.
- Relate arquivos alterados, comandos executados, resultados observados e limitações.
- Pare ao terminar a fase/tarefa. Não inicie a próxima automaticamente.

Use ciclo Red → Green → Refactor → Verify quando aplicável. Não declare testes aprovados se não foram executados.

## 3. Arquitetura obrigatória

- Produto dos jogadores exclusivamente mobile: Android e iOS.
- Cliente mobile em React Native + TypeScript, sujeito a prova técnica de módulos nativos antes de fixar bibliotecas.
- Backend Python + FastAPI em monólito modular.
- PostgreSQL + PostGIS é a fonte oficial da verdade.
- Redis é auxiliar: cache, rate limiting, presença e distribuição efêmera de eventos. Nunca é autoridade para partidas, resultados ou rating.
- Workers são processos separados, mas não microserviços independentes no MVP.
- O aplicativo conversa com o backend por contratos HTTP/WebSocket versionados. Nunca acessa o banco diretamente.
- Não criar site público para jogadores.
- Um domínio técnico pode ser necessário para associações de passkeys e arquivos `.well-known`; isso não autoriza criar uma interface web pública.
- Não adicionar Kafka, Kubernetes ou microserviços sem evidência de necessidade e uma ADR aprovada.

## 4. Segurança e privacidade: invariantes

- Toda autorização é verificada no servidor, em cada recurso e operação. UUID não substitui autorização.
- Telefone verificado é identificador de contato, não prova de identidade civil nem prova de pessoa única.
- A identidade interna usa UUID; telefone nunca é chave primária.
- OTP é temporário, de uso único, limitado, armazenado de forma protegida e nunca registrado em logs.
- Passkeys são o método preferencial; SMS não é o único mecanismo de recuperação de conta.
- Segredos nunca entram no Git, em logs, no bundle mobile ou em arquivos `.env` versionados. Só `.env.example` com placeholders.
- Tokens de renovação devem ser rotativos, revogáveis e armazenados no servidor somente como hash.
- Dados pessoais e localização devem ser minimizados. Não implementar rastreamento contínuo em segundo plano no MVP.
- Toda entrada externa é validada no backend. Usar queries parametrizadas, limites de tamanho, paginação e rate limiting.
- Não confiar em MMR, Trust Factor, papel, estado de conta, resultado ou permissões enviados pelo cliente.
- Ações administrativas e alterações competitivas precisam de autorização, justificativa e auditoria.
- Uploads/evidências devem ter tipo, tamanho, autorização e retenção controlados; armazenamento privado.

## 5. Integridade competitiva

- O backend é o único responsável por formar partidas, validar transições, aceitar resultados e calcular rating.
- Partidas e resultados são transacionais e idempotentes.
- Uma partida em disputa não altera MMR.
- MMR é separado por modalidade/formato e nunca é editável pelo cliente ou diretamente pelo painel.
- Histórico de rating e auditoria são append-only; correções são eventos compensatórios, não exclusões silenciosas.
- Trust Factor é separado de MMR. Denúncia isolada não gera punição automática.
- Redis, push, WebSocket e GPS não são prova de estado competitivo ou presença por si sós.
- Proteger filas e formação de partidas contra concorrência, duplicidade e condições de corrida usando transações e constraints do PostgreSQL.

## 6. Organização e limites de código

- Separar `mobile/`, `backend/`, `infra/`, `docs/` e `harness/`.
- Organizar por domínio; evitar arquivos gigantes, dependências circulares e camadas genéricas sem necessidade.
- Rotas HTTP devem ser finas; regras de negócio pertencem a casos de uso/serviços do domínio.
- Schemas de entrada/saída explícitos; não retornar entidades ORM diretamente.
- Toda alteração de banco passa por migração Alembic revisável. Não editar schema de produção manualmente.
- Não introduzir abstrações, dependências ou padrões antes de uma necessidade concreta.
- Fixar versões e manter lockfiles. Atualizações de dependência devem ser justificadas e testadas.
- Não fazer refatoração ampla junto com uma feature, salvo necessidade demonstrada.

## 7. Testes e qualidade

- Testar regras de domínio sem depender de rede ou serviços reais.
- Testes de integração usam banco de teste isolado e exercitam constraints/migrações.
- Testar autorização negativa (usuário A não acessa recursos do usuário B).
- Testar idempotência, concorrência, repetição de eventos e falhas de dependências.
- Para autenticação, testar expiração, replay, limite de tentativas, rotação, revogação e recuperação.
- Para partidas/rating, testar estados inválidos, submissões simultâneas, disputas e aplicação única do rating.
- Não desabilitar testes, type checks, lint ou verificações de segurança para fazer CI passar.
- Não reduzir cobertura de uma regra crítica sem justificar e propor compensação.

## 8. Git e ações externas

- `main` deve permanecer sempre em estado verificável.
- Use branches curtas `feat/<fase>-<assunto>`, `fix/<assunto>` ou `docs/<assunto>`.
- Não force push, não reescreva histórico e não use comandos destrutivos como `git reset --hard` ou `git checkout --` sem pedido explícito.
- Não faça commit, push, merge, release, deploy, migração em ambiente compartilhado nem alteração de serviço externo sem autorização explícita para aquela ação.
- Nunca use credenciais reais em ambiente de teste. Solicite autorização antes de acessar sistemas externos ou gerar custos (SMS, mapas, hospedagem etc.).

## 9. Relatório obrigatório ao concluir

Apresente:
1. O que foi feito e o que ficou fora do escopo.
2. Arquivos criados/alterados.
3. Testes e comandos realmente executados, com resultado.
4. Riscos, limitações e decisões pendentes.
5. Como reproduzir a validação.
6. Confirmação de que não iniciou a próxima fase e não executou ações externas não autorizadas.
