# Objetivos do produto — JOGA

## Propósito

Criar o JOGA, um aplicativo mobile que conecte jogadores de esportes presenciais, forme partidas e equipes equilibradas e mantenha uma experiência casual/competitiva confiável. O produto também inclui comunidade (lobbies, amigos, clãs), descoberta de espaços e **reserva de quadras com crédito pré-pago e pagamento avulso**, conforme a referência máxima em `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` e a decisão vigente da ADR 0049.

## Resultados desejados

1. Um jogador consegue criar e proteger uma conta usando telefone verificado e passkey.
2. Um jogador consegue configurar modalidades, formatos, nível inicial, disponibilidade e região.
3. O jogador consegue encontrar partidas compatíveis por proximidade, com localização em primeiro plano ou seleção manual de região.
4. O sistema forma partidas sem duplicar participantes ou perder entradas em cenários concorrentes.
5. Participantes conseguem confirmar presença, relatar resultados e contestar divergências.
6. O rating é atualizado exclusivamente pelo backend, uma única vez por partida válida, com histórico auditável.
7. Sinais de confiabilidade são tratados separadamente da habilidade esportiva.
8. Um grupo consegue solicitar uma quadra, obter bloqueio temporário e quitar as vagas por crédito ou, no fluxo avulso, por Pix individual, dentro do prazo.
9. A reserva só é confirmada com todas as vagas quitadas e o bloqueio confirmado pelo estabelecimento.
10. Falhas de SMS, push, Redis ou WebSocket não corrompem partidas, resultados, reservas ou rating.
11. O produto protege dados pessoais, telefone, localização e dados financeiros, respeitando a LGPD.

## Escopo do produto

Referência máxima: `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` (seção 3). O produto segue três pilares, com confiança como camada transversal:

1. **Competitividade:** matchmaking, partidas casuais e ranqueadas, MMR, rankings individuais e troféus de clã por modalidade.
2. **Comunidade:** lobbies, chat por contexto, lista de amigos, convites e clãs, com moderação dedicada.
3. **Infraestrutura esportiva e reservas:** descoberta de locais públicos e privados, solicitação de reserva, bloqueio temporário, compra de crédito em reais exibida em tickets, pagamento avulso individual, confirmação e repasse ao fornecedor.

A camada transversal reúne identidade, autorização, auditoria, notificações, prazos controlados pelo servidor, prevenção de abuso e transparência de preços.

A execução é dividida nas fases de `PLANS.md`. O MVP do núcleo esportivo corresponde às fases 0–10; reservas, interface financeira do fornecedor, clãs, moderação e publicidade têm fases próprias (11+). Clãs e troféus integram o MVP pela ADR 0044 e devem estar concluídos antes da 19.

## Fora do escopo do produto

- Site público para jogadores/consumidores.
- App nativo separado para gerenciadores.
- Comércio de produtos (marketplace), catálogo, estoque, pedidos, vendedores, entregas e código de recebimento de produtos.
- ERP completo, gestão de vendas presenciais do estabelecimento e integrações PDV.
- Processador de pagamentos próprio ou carteira custodial.
- Logística própria: cotação de frete, transportadoras, etiquetas e rastreamento centralizado.
- Chat global universal e upload livre de mídia em chats.
- Premium ou publicidade com vantagens competitivas.
- Microserviços, Kafka e Kubernetes.
- Localização em segundo plano contínua.

## Fora do escopo do MVP (fases 0–10)

- Organizações, painel de gestão web e onboarding de fornecedores (fase 11).
- Quadras, agenda, disponibilidade e cadastro do fornecedor (fase 12).
- Reservas, temporizadores, bloqueio e máquina de estados (fase 13).
- Pagamentos Pix, compra de crédito, PSP, webhooks e reembolsos (fases 14/14E).
- Crédito, carteira, temporada e NFS-e (fase 14D/14E).
- Interface financeira do fornecedor, repasse e conciliação (fase 15).
- Clãs, troféus e temporadas (fase 16).
- Moderação dedicada e Trust & Safety (fase 17).
- Publicidade (fase 18).
- Jurídico/fiscal/LGPD (fase 19A) e hardening final (fase 19B).
- Aluguel de equipamentos, gestão completa de academias/clubes, intermediação de profissionais e torneios: exclusões do escopo atual do conceito (seção 22) — reavaliar como decisão de produto antes de qualquer implementação.

## Restrições não negociáveis

- A API é a única interface de acesso do aplicativo aos dados do produto.
- PostgreSQL é a fonte de verdade.
- Nenhuma regra competitiva crítica é decidida pelo cliente.
- Autenticação e autorização são diferentes e ambas são obrigatórias.
- Telefone não é identidade civil nem garantia de uma pessoa por conta.
- Localização deve ser minimizada, contextual e opcional para fluxos que aceitam região manual.
- O sistema deve ser idempotente, auditável e testável sob concorrência.
- O backend controla prazos, estados de reserva e confirmação financeira; o cliente não é autoridade.
- A quadra recebe o repasse após a confirmação e a quitação, em `starts_at + 2h` (ADR 0040), independentemente de a partida ser declarada realizada.
- Fornecedor sem chave de repasse validada não pode originar reserva paga; o KYC contratual do modelo C pertence à fase comercial.
- Não declarar segurança absoluta; usar controles em camadas, testes e monitoramento.

## Critérios de sucesso do MVP

- Fluxo de cadastro/autenticação demonstrável em Android e iOS, inclusive recuperação e revogação de sessão.
- Usuário pode negar GPS ou usar localização aproximada e ainda pesquisar por região manual.
- Duas requisições simultâneas não criam entradas duplicadas nem partidas duplicadas.
- Usuário não consegue consultar/alterar recursos de outro usuário sem autorização.
- Resultado divergente não altera rating.
- Reprocessamento de evento não duplica aplicação de MMR.
- Testes de unidade, integração, autorização e concorrência passam no CI.
- Backups e restauração são testados antes de produção.
- Não existem segredos reais no repositório ou nos artefatos mobile.

## Decisões ainda pendentes

- EAS Build, distribuição e OTA, após a decisão por Expo development build com `expo prebuild` (ADR 0009).
- Biblioteca e fluxo concreto de passkeys em Android e iOS.
- Provedor de SMS e política de custo/abuso.
- Domínio técnico e hospedagem dos arquivos de associação de plataforma.
- Provedor de mapas/geocodificação e custos/licenças.
- PSP: Mercado Pago no protótipo com jogadores reais (ADR 0048); Inter PJ e Pagar.me no futuro. Tarifas, repasse, MED, chargeback e conciliação precisam de confirmação formal.
- Janela de contestação após o repasse e tratamento de divergência; o repasse em si está definido em `starts_at + 2h` (ADR 0040).
- Política de cancelamento após a reserva confirmada e desistência individual.
- Framework e estratégia de deploy do painel web de gestão (React + Vite, ADR 0028); falta ambiente de produção.
- Infraestrutura e região de hospedagem após estimativa de tráfego, custo e requisitos LGPD.
- Regra de confirmação de resultados por modalidade: implementada no backend na Fase 7 e validada com PostgreSQL local. Retenção provisória no ADR 0024; revisão definitiva na fase de LGPD. Pendente: configurar operadores autorizados da CLI.
- Política de moderação, limites de contexto e retenção de mensagens.
- Parâmetros iniciais do rating e da fórmula de troféus, a validar com simulações e testes.
- Parâmetros medidos de `q`, `C_k`, `C_c`, `τ` e `p_t` para a fórmula de precificação.
- ADR 0049: pareceres fiscal e jurídico, custódia C, CPF, NFS-e, percentual final da taxa e política de reembolso de passe/pacote.
- Acesso por quadra (ACL) versus permissão por organização.
- Marca, bundle/package IDs, SMS, mapas e storage de produção.

A lista completa de pendências e fases responsáveis está em `docs/PENDENCIAS.md`.
