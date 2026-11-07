# Threat model — núcleo esportivo (Fase 10A)

**Data:** 2026-11-06
**Escopo:** identidade, perfil/descoberta, fila/matchmaking, partidas, resultados/disputas, rating, chat/social e Outbox, no backend e app mobile em desenvolvimento.
**Fora do escopo:** reservas, pagamentos, PSP, KYC, painel de estabelecimentos, clãs, publicidade e produção comercial.

## Ativos

- Contas, telefone, passkeys, sessões e dispositivos.
- Perfil esportivo, disponibilidade e região aproximada.
- Filas, lobbies, partidas, presença e histórico competitivo.
- Relatos, evidências, decisões de disputa e MMR.
- Mensagens de lobby, amizades, bloqueios e convites.
- Tokens de push, IDs de idempotência e eventos de Outbox.
- Segredos de aplicação, credenciais de banco e logs.

## Atores

- Jogador autenticado legítimo.
- Jogador malicioso ou conta comprometida.
- Usuário não autenticado.
- Operador interno de revisão.
- Processo worker confiável.
- Provedor externo futuro (SMS, push, mapas).

## Fronteiras de confiança

1. App mobile → API HTTP/WebSocket: não confiável; toda entrada é validada.
2. API → PostgreSQL/Redis: confiável, mas sujeita a concorrência e falhas.
3. Workers → PostgreSQL: confiáveis, mas idempotência e locks são obrigatórios.
4. Operador → CLI: confiável apenas se o ambiente e a lista de operadores estiverem protegidos.
5. Provedores externos → API: não confiáveis até validação criptográfica/autenticação.

## Ameaças e controles

| Ameaça | Exemplo | Controles atuais | Risco residual |
|---|---|---|---|
| Acesso a objeto de outro usuário (BOLA) | Ler partida, chat, perfil ou resultado alheio | autorização por recurso em todos os endpoints; testes negativos | cobertura manual de novos endpoints |
| Sequestro/replay de sessão | Reutilizar access/refresh token | hash de tokens, rotação, revogação, expiração curta | TTL de access ainda curto; refresh no mobile não é automático |
| Abuso de OTP/SMS | Enumerar telefones, reenviar códigos, testar códigos | HMAC de telefone, cooldown, limites por telefone/IP, uso único, sem OTP em logs | limite de verificação por IP ainda incompleto |
| Manipulação de resultado/rating | Votar várias vezes, forjar vencedor, editar MMR | elegíveis congelados, idempotência, quórum, revisão humana, rating no servidor, eventos append-only | conluio coordenado exige análise humana |
| Concorrência em partidas/rating | Dois workers fechando rodada ou aplicando rating | locks de linha, constraints únicas, transações, testes PostgreSQL | testes de carga ainda limitados |
| Abuso de chat | Flood, spam, assédio, mensagem gigante | autenticação, participação no lobby, limite de 2.000 caracteres, rate limit, sem mídia | moderação de conteúdo fica para Fase 17 |
| Convites abusivos | Spam de convites, convite a bloqueado | amizade obrigatória, bloqueio, limite por hora, unicidade, capacidade do lobby | denúncia de convite ainda não existe |
| WebSocket não autorizado | Assinar lobby alheio, sessão revogada | handshake autenticado, autorização por lobby, heartbeat/revalidação | entrega local; sem Redis/fan-out |
| Vazamento em logs | Tokens, telefone, query string, corpo | logs sem query string/corpo; request ID; revisão de eventos | revisão contínua necessária |
| Push token exposto | Token em resposta/log de outro usuário | token privado, único, revogável, sem listagem pública | provedor real ainda não configurado |
| Outbox duplicada/perdida | Evento entregue duas vezes ou parado | gravação transacional, status, idempotência do consumidor | dispatcher/push real pendente |
| Backup indisponível/corrompido | Perda de dados locais | `pg_dump`/`pg_restore` documentados e testados | produção exige storage externo, criptografia e RPO/RTO |
| Dependência vulnerável | Biblioteca com CVE | versões fixadas, CI, revisão de lockfile | auditoria automatizada de CVE ainda pendente |
| Enumeração de usuários | Buscar usuários/perfis livremente | sem endpoint global de busca; dados sociais limitados às relações | ranking expõe nome/divisão; revisar privacidade |
| Abuso de recursos | Payload grande, muitas conexões, carga | limites de tamanho, rate limiting parcial, timeouts | rate limit global e proteção de borda pendentes |
| Acesso cruzado entre organizações (BOLA) | Membro de uma organização lê ou altera membros, estabelecimentos ou auditoria de outra | vínculo obrigatório, capacidade por papel, consulta sempre escopada pela organização, 404 para não-membro e testes BOLA | painel web e recursos de reservas/financeiro ainda não existem |
| Abuso de identidade visual | Foto de terceiro, avatar ofensivo, impersonação | sem fotos de pessoas; avatar de catálogo fechado validado pelo backend; nome/tag moderados; denúncia de perfil | catálogo e critérios de moderação ainda pendentes |
| Sequestro de sessão web | XSS, CSRF ou vazamento de refresh token | refresh em cookie `HttpOnly`/`SameSite=Strict`, access só em memória, CSRF de duplo envio em refresh/logout, `Secure` em produção, CSP estrita no build | cabeçalhos de `frame-ancestors`/HSTS na hospedagem e revisão dedicada de XSS pendentes |

## Controles transversais

- Autorização no servidor em cada recurso e operação.
- IDs UUID não substituem autorização.
- Consultas de organização filtram pelo vínculo do usuário e pela organização proprietária do recurso.
- Validação e limites de entrada em todos os schemas.
- Queries parametrizadas via SQLAlchemy.
- Idempotência em operações críticas.
- Constraints e transações no PostgreSQL.
- Segredos fora do Git; `.env` não versionado.
- Logs sem PII, tokens, OTP, query string ou corpo.
- Health live/ready e request ID para operação.
- Erros do painel exibem o `X-Request-ID` como referência de suporte, sem detalhes internos.
- Painel com CSP estrita no build, testes de UI automatizados e error boundary.
- Retenção provisória e limpeza manual documentadas.
- Fotos de quadra entram apenas por fluxo autenticado de organização, com revisão e sem pessoas identificáveis.

## Riscos residuais e bloqueios

- **Alto:** revisão LGPD/jurídica definitiva ainda não feita.
- **Alto:** backup/restore de produção, criptografia e storage externo não definidos.
- **Médio:** rate limiting global/borda e proteção contra abuso distribuído incompletos.
- **Médio:** Redis/fan-out multi-processo e múltiplas instâncias não implementados.
- **Médio:** push real e SMS dependem de provedor/credenciais.
- **Médio:** cabeçalhos de segurança da hospedagem do painel (`frame-ancestors`, HSTS, `Permissions-Policy`) ainda não configurados.
- **Médio:** moderação de chat e denúncias pertencem à Fase 17.
- **Médio:** catálogo de avatares e moderação de nome/avatar pertencem à Fase 17.
- **Baixo:** cobertura de UI mobile e testes em aparelho são manuais.

## Critérios para piloto

1. Restore local reproduzível e documentado.
2. Testes de carga local sem falhas críticas.
3. Nenhuma vulnerabilidade crítica/alta conhecida sem bloqueio explícito.
4. Limites de custo de SMS/mapas/infra definidos.
5. Responsável por incidentes e rollback definidos.
6. LGPD e retenção revisadas antes de dados reais.
