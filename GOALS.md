# Objetivos do produto — JOGA

## Propósito

Criar o JOGA, um aplicativo mobile que conecte jogadores de esportes presenciais, forme partidas e equipes equilibradas e mantenha uma experiência casual/competitiva confiável. O produto também inclui comunidade (lobbies, amigos, clãs), descoberta de espaços e **reserva de quadras com pagamento individual**, conforme a referência máxima em `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`.

## Resultados desejados

1. Um jogador consegue criar e proteger uma conta usando telefone verificado e passkey.
2. Um jogador consegue configurar modalidades, formatos, nível inicial, disponibilidade e região.
3. O jogador consegue encontrar partidas compatíveis por proximidade, com localização em primeiro plano ou seleção manual de região.
4. O sistema forma partidas sem duplicar participantes ou perder entradas em cenários concorrentes.
5. Participantes conseguem confirmar presença, relatar resultados e contestar divergências.
6. O rating é atualizado exclusivamente pelo backend, uma única vez por partida válida, com histórico auditável.
7. Sinais de confiabilidade são tratados separadamente da habilidade esportiva.
8. Um grupo consegue solicitar uma quadra, obter bloqueio temporário e pagar individualmente por Pix dentro do prazo.
9. A reserva só é confirmada com todos os pagamentos aprovados e o bloqueio confirmado pelo estabelecimento.
10. Falhas de SMS, push, Redis ou WebSocket não corrompem partidas, resultados, reservas ou rating.
11. O produto protege dados pessoais, telefone, localização e dados financeiros, respeitando a LGPD.

## Escopo do produto

Referência máxima: `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` (seção 3). O produto segue três pilares, com confiança como camada transversal:

1. **Competitividade:** matchmaking, partidas casuais e ranqueadas, MMR, rankings individuais e troféus de clã por modalidade.
2. **Comunidade:** lobbies, chat por contexto, lista de amigos, convites e clãs, com moderação dedicada.
3. **Infraestrutura esportiva e reservas:** descoberta de locais públicos e privados, solicitação de reserva, bloqueio temporário, pagamento Pix individual, confirmação e liberação do valor ao estabelecimento.

A camada transversal reúne identidade, autorização, auditoria, notificações, prazos controlados pelo servidor, prevenção de abuso e transparência de preços.

A execução é dividida nas fases de `PLANS.md`. O MVP do núcleo esportivo corresponde às fases 0–10; reservas, interface financeira do estabelecimento, clãs, moderação e publicidade têm fases próprias (11+).

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

- Organizações, painel de gestão web e onboarding de estabelecimentos (fase 11).
- Quadras, agenda, disponibilidade e KYC do recebedor (fase 12).
- Reservas, temporizadores, bloqueio e máquina de estados (fase 13).
- Pagamentos Pix, split, PSP, webhooks e reembolsos (fase 14).
- Interface financeira do estabelecimento, liberação e conciliação (fase 15).
- Clãs, troféus e temporadas (fase 16).
- Moderação dedicada e Trust & Safety (fase 17).
- Publicidade (fase 18).
- Hardening final e lançamento comercial (fase 19).
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
- A quadra só recebe a liberação depois da confirmação da reserva e da realização da partida.
- Estabelecimento sem recebedor ativo (KYC) não pode originar reserva paga.
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
- PSP: Pagar.me Flex como primeira opção condicionada e Inter como alternativa centralizada; tarifas, saque autônomo, estorno Pix com split, MED e KYC precisam de confirmação formal (ADR 0021).
- Valor de `N` para liberação automática após a partida e janela de disputa.
- Política de cancelamento após a reserva confirmada e desistência individual.
- Framework e estratégia de deploy do painel web de gestão.
- Infraestrutura e região de hospedagem após estimativa de tráfego, custo e requisitos LGPD.
- Regra de confirmação de resultados por modalidade, tolerância de divergências e prazos de relato (faixa de 5 a 10 minutos; valor de segunda rodada de desempate pendente). Tratamento de empate exato em 50% está definido (conceito §9.4; ADR 0008).
- Política de moderação, limites de contexto e retenção de mensagens.
- Parâmetros iniciais do rating e da fórmula de troféus, a validar com simulações e testes.
- Parâmetros medidos de `q`, `C_k`, `C_c`, `τ` e `p_t` para a fórmula de precificação.

A lista completa de pendências e fases responsáveis está em `docs/JOGA_DOCUMENTACAO_TECNICA.md`, seção 26.
