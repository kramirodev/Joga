# Objetivos do produto — JOGA

## Propósito

Criar o JOGA, um aplicativo mobile que conecte jogadores de esportes presenciais, forme partidas e equipes equilibradas e mantenha uma experiência casual/competitiva confiável.

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

- Aplicativos Android e iOS.
- Backend FastAPI e workers.
- PostgreSQL + PostGIS; Redis como componente auxiliar.
- Cadastro por telefone verificado, passkeys e sessões seguras.
- Perfil, modalidades, disponibilidade, locais e busca geográfica.
- Filas casuais/ranqueadas, matchmaking e partidas.
- Confirmação, resultado, disputas, rating, Trust Factor e notificações.

## Fora do escopo inicial

- Site público para jogadores.
- Marketplace, reservas ou pagamentos de quadras.
- Chat privado completo.
- Premium com vantagens competitivas.
- Microserviços, Kafka e Kubernetes.
- ML antifraude, temporadas complexas e torneios avançados.
- Localização em segundo plano contínua.

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

- Expo com development builds ou React Native CLI, a decidir após protótipo nativo.
- Biblioteca e fluxo concreto de passkeys em Android e iOS.
- Provedor de SMS e política de custo/abuso.
- Domínio técnico e hospedagem dos arquivos de associação de plataforma.
- Provedor de mapas/geocodificação e custos/licenças.
- Infraestrutura e região de hospedagem após estimativa de tráfego, custo e requisitos LGPD.
- Regra de confirmação de resultados por modalidade.
- Parâmetros iniciais do rating, a validar com simulações e testes.
