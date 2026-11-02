# Objetivos do produto — JOGA

## Propósito

Criar o JOGA, um aplicativo mobile que conecte jogadores de esportes presenciais, forme partidas e equipes equilibradas e mantenha uma experiência casual/competitiva confiável. O produto também inclui comunidade (lobbies, amigos, clãs), descoberta e reserva de quadras/espaços e marketplace de produtos, conforme a referência máxima em `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`.

## Resultados desejados

1. Um jogador consegue criar e proteger uma conta usando telefone verificado e passkey.
2. Um jogador consegue configurar modalidades, formatos, nível inicial, disponibilidade e região.
3. O jogador consegue encontrar partidas compatíveis por proximidade, com localização em primeiro plano ou seleção manual de região.
4. O sistema forma partidas sem duplicar participantes ou perder entradas em cenários concorrentes.
5. Participantes conseguem confirmar presença, relatar resultados e contestar divergências.
6. O rating é atualizado exclusivamente pelo backend, uma única vez por partida válida, com histórico auditável.
7. Sinais de confiabilidade são tratados separadamente da habilidade esportiva.
8. Falhas de SMS, push, Redis ou WebSocket não corrompem partidas, resultados ou rating.
9. O produto protege dados pessoais, telefone e localização, respeitando a LGPD.

## Escopo do produto

Referência máxima: `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` (seção 3). O produto completo segue os quatro pilares do conceito:

1. **Competitividade:** matchmaking, partidas casuais e ranqueadas, MMR, rankings individuais e troféus de clã por modalidade.
2. **Social:** lobbies, chat por lobby, lista de amigos, convites e clãs, com moderação dedicada.
3. **Infraestrutura esportiva:** descoberta de locais públicos e privados, agenda e reserva de quadras particulares.
4. **Comércio:** marketplace de produtos, pedidos, pagamentos, retirada/entrega pelo vendedor, resolução de disputas comerciais; painel web de gestão (JOGA y GESTÃO) para as operações originadas no JOGA.

A execução é dividida nas fases de `PLANS.md`. O MVP do núcleo esportivo corresponde às fases 0–10; os módulos comerciais e sociais avançados têm fases próprias (11+).

## Fora do escopo do produto

- Site público para jogadores/consumidores.
- App nativo separado para gerenciadores.
- ERP completo, gestão de vendas presenciais do estabelecimento e integrações PDV.
- Processador de pagamentos próprio ou carteira custodial.
- Logística própria: cotação de frete, transportadoras, etiquetas e rastreamento centralizado.
- Chat global universal e upload livre de mídia em chats.
- Premium ou publicidade com vantagens competitivas.
- Microserviços, Kafka e Kubernetes.
- Localização em segundo plano contínua.

## Fora do escopo do MVP (fases 0–10)

- Marketplace, catálogo, estoque, pedidos e pagamentos (fases 12–13).
- Painel de gestão web e organizações comerciais (fase 11).
- Quadras privadas com reserva paga (fase 14).
- Clãs, troféus e temporadas (fase 16).
- Moderação dedicada e Trust & Safety (fase 17).
- Publicidade (fase 18).
- Aluguel de equipamentos, gestão completa de academias/clubes, marketplace de profissionais, torneios: exclusões do escopo atual do conceito (seção 16) — reavaliar como decisão de produto antes de qualquer implementação.

## Restrições não negociáveis

- A API é a única interface de acesso do aplicativo aos dados do produto.
- PostgreSQL é a fonte de verdade.
- Nenhuma regra competitiva crítica é decidida pelo cliente.
- Autenticação e autorização são diferentes e ambas são obrigatórias.
- Telefone não é identidade civil nem garantia de uma pessoa por conta.
- Localização deve ser minimizada, contextual e opcional para fluxos que aceitam região manual.
- O sistema deve ser idempotente, auditável e testável sob concorrência.
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
- Provedor de pagamentos (PSP), split e política de disputas/chargebacks.
- Framework e estratégia de deploy do painel web de gestão.
- Infraestrutura e região de hospedagem após estimativa de tráfego, custo e requisitos LGPD.
- Regra de confirmação de resultados por modalidade, tolerância de divergências e prazos de relato (faixa de 5 a 10 minutos; valor de segunda rodada de desempate pendente). Tratamento de empate exato em 50% está definido (conceito §9.4; ADR 0008).
- Política de moderação, limites de contexto e retenção de mensagens.
- Parâmetros iniciais do rating e da fórmula de troféus, a validar com simulações e testes.

A lista completa de pendências e fases responsáveis está em `docs/JOGA_DOCUMENTACAO_TECNICA.md`, seção 26.
