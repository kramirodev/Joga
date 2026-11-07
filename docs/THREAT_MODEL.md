# Threat model — núcleo esportivo e painel de gestão (Fases 10–12A)

**Data:** 2026-11-07
**Escopo:** identidade, perfil/descoberta, fila/matchmaking, partidas, resultados/disputas, rating, chat/social, Outbox, organizações, painel web, quadras, agenda e fotos de quadra, no backend e app mobile em desenvolvimento.
**Fora do escopo:** reservas, pagamentos, PSP, KYC, clãs, publicidade e produção comercial.

## Ativos

- Contas, telefone, passkeys, sessões e dispositivos.
- Perfil esportivo, disponibilidade e região aproximada.
- Filas, lobbies, partidas, presença e histórico competitivo.
- Relatos, evidências, decisões de disputa e MMR.
- Mensagens de lobby, amizades, bloqueios e convites.
- Tokens de push, IDs de idempotência e eventos de Outbox.
- Organizações, vínculos, estabelecimentos, quadras, agenda e preços.
- Fotos de quadra, arquivos privados e metadados de revisão.
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
2. Painel web → API HTTP: não confiável; cookie, CSRF e CSP reduzem abuso.
3. API → PostgreSQL/Redis: confiável, mas sujeita a concorrência e falhas.
4. Workers → PostgreSQL: confiáveis, mas idempotência e locks são obrigatórios.
5. Operador → CLI: confiável apenas se o ambiente e a lista de operadores estiverem protegidos.
6. API → storage de fotos: privado; o arquivo nunca é servido estaticamente.
7. Provedores externos → API: não confiáveis até validação criptográfica/autenticação.

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
| Acesso cruzado entre organizações (BOLA) | Membro de uma organização lê ou altera membros, estabelecimentos, quadras, fotos ou auditoria de outra | vínculo obrigatório, capacidade por papel, consulta sempre escopada pela organização, 404 para não-membro e testes BOLA | recursos de reservas/financeiro ainda não existem |
| Upload de imagem maliciosa | Polyglot, malware, decompression bomb, EXIF com localização, arquivo acima do limite | validação real por Pillow, reencode JPEG, remoção de EXIF, limites de bytes/pixels/dimensões, storage privado e serving autorizado | antivírus dedicado e storage de produção pendentes |
| Abuso de revisão de foto | Organização aprovar conteúdo impróprio ou foto com pessoa | revisão por `OWNER`/`ADMIN`, motivo obrigatório na rejeição, auditoria, `OPERATOR` sem revisão | revisão independente e denúncia de foto pertencem à Fase 17 |
| Dupla reserva | Dois aceites concorrentes para o mesmo espaço/intervalo | lock da linha do espaço, verificação transacional de holds/reservas, teste PostgreSQL concorrente | exclusão por intervalo no banco ainda não usada; cobertura por serviço |
| Timer adulterado ou reiniciado | Cliente tentar prorrogar T1/T2/T3 ou agir após o prazo | prazos no backend, timers independentes, rejeição após deadline, worker idempotente | T2 em horário comercial pendente |
| Pagamento simulado exposto | Usar endpoint de simulação em produção | rota só permite ambiente local/teste/development/ci | revisão de configuração de deploy necessária |
| Acesso indevido a reserva | Participante ou organização consultar reserva alheia | autorização por participante/organização em cada rota | testes contínuos a cada novo endpoint |
| Custódia centralizada no beta | Dinheiro real ficar na conta do JOGA sem retenção/split de produção | escopo restrito a protótipo/beta de teste, ledger interno, repasse após `COMPLETED`, CNPJ/MEI e revisão jurídica para dinheiro real | risco jurídico/regulatório se o beta operar dinheiro real sem validação |
| Troca de PSP sem abstração | Domínio acoplado ao Mercado Pago e difícil migrar para Pagar.me | adaptador de PSP com modos `mercadopago_beta` e `pagarme_production` | implementação da Fase 14 ainda não iniciada |
| Webhook de pagamento forjado/replay | Confirmar reserva sem pagamento real | assinatura HMAC, consulta server-to-server, `psp_webhook_events` idempotente e ledger append-only | segredo e URL de produção ainda não configurados |
| Divergência de valor/referência | PSP devolver valor diferente da cobrança | conferência de `amount_cents` e `external_reference` antes de aplicar status | conciliação periódica pertence à Fase 15 |
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
- Fotos de quadra são validadas pelo conteúdo real, reencodadas em JPEG, têm EXIF removido e são servidas por endpoint autenticado com `no-store`.
- A revisão inicial de foto é restrita a `OWNER`/`ADMIN` e auditada; `OPERATOR` não revisa.
- Reservas são escopadas por participante ou organização; hold e confirmação usam lock transacional.
- T1/T2/T3 são registrados em timers independentes; o pagamento simulado é bloqueado fora de ambiente local/teste.

## Riscos residuais e bloqueios

- **Alto:** revisão LGPD/jurídica definitiva ainda não feita.
- **Alto:** backup/restore de produção, criptografia e storage externo não definidos.
- **Médio:** rate limiting global/borda e proteção contra abuso distribuído incompletos.
- **Médio:** Redis/fan-out multi-processo e múltiplas instâncias não implementados.
- **Médio:** push real e SMS dependem de provedor/credenciais.
- **Médio:** cabeçalhos de segurança da hospedagem do painel (`frame-ancestors`, HSTS, `Permissions-Policy`) ainda não configurados.
- **Médio:** moderação de chat e denúncias pertencem à Fase 17.
- **Médio:** catálogo de avatares e moderação de nome/avatar pertencem à Fase 17.
- **Médio:** revisão de foto de quadra ainda é feita pela própria organização; revisão independente e denúncia de foto pertencem à Fase 17.
- **Médio:** storage de fotos é local; provedor de produção, criptografia, backup e limpeza de órfãos não definidos.
- **Médio:** T2 de reservas usa tempo corrido; horário comercial, feriados e dias fechados pendentes.
- **Médio:** pagamento de reserva é simulado; PSP real, webhooks e reembolso pertencem à Fase 14.
- **Médio:** no protótipo/beta, a custódia é centralizada e de teste; dinheiro real exige CNPJ/MEI, contrato e revisão jurídica.
- **Médio:** produção depende de contratação do Pagar.me e validação de retenção/split/reembolso.
- **Médio:** webhook do Mercado Pago ainda não foi validado com credenciais sandbox reais; testes usam HTTP simulado.
- **Médio:** e-mail do pagador é obrigatório na Orders API e o cadastro atual é por telefone.
- **Baixo:** cobertura de UI mobile e testes em aparelho são manuais.

## Critérios para piloto

1. Restore local reproduzível e documentado.
2. Testes de carga local sem falhas críticas.
3. Nenhuma vulnerabilidade crítica/alta conhecida sem bloqueio explícito.
4. Limites de custo de SMS/mapas/infra definidos.
5. Responsável por incidentes e rollback definidos.
6. LGPD e retenção revisadas antes de dados reais.
