# Threat model — núcleo esportivo, reservas, pagamentos e painel de gestão

**Data:** 2026-11-16
**Escopo:** identidade, perfil/descoberta, fila/matchmaking, partidas, resultados/disputas, rating, chat/social, Outbox, organizações, painel web, quadras, agenda, reservas, pagamentos, crédito, ledger, moderação, clãs e custódia B→C, no backend, app mobile e painel.
**Fora do escopo:** produção comercial com dinheiro real, escrow contratado, publicidade e operação de NFS-e. Esses itens estão bloqueados pela ADR 0049 e pela Fase 19A.

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
| Sequestro/replay de sessão | Reutilizar access/refresh token | hash de tokens, rotação, revogação, expiração curta, refresh automático no app | limite por dispositivo e reauth de operações sensíveis pendentes |
| Abuso de OTP/SMS | Enumerar telefones, reenviar códigos, testar códigos | HMAC de telefone, cooldown, limites por telefone/IP, uso único, sem OTP em logs | limite por dispositivo; enumeração na troca de telefone |
| Manipulação de resultado/rating | Votar várias vezes, forjar vencedor, editar MMR | elegíveis congelados, idempotência, quórum, revisão humana, rating no servidor, eventos append-only | conluio coordenado exige análise humana |
| Exposição de dados competitivos | Vazar MMR bruto por endpoint, ranking, perfil ou painel de rede; inferir nível individual a partir de célula de rede | MMR bruto não é retornado por nenhum endpoint; app mostra divisão/progresso; ranking e perfil alheio sem MMR; sem MMR de adversário antes da partida; rede só agregada e com amostra mínima | agregações pequenas ainda podem sugerir proximidade; calibrar amostra no piloto |
| Concorrência em partidas/rating | Dois workers fechando rodada ou aplicando rating | locks de linha, constraints únicas, transações, testes PostgreSQL | testes de carga ainda limitados |
| Abuso de chat | Flood, spam, assédio, mensagem gigante | autenticação, participação no lobby, limite de 2.000 caracteres, rate limit, sem mídia | moderação de conteúdo existe parcialmente; classificador local pendente |
| Convites abusivos | Spam de convites, convite a bloqueado | amizade obrigatória, bloqueio, limite por hora, unicidade, capacidade do lobby | denúncia de convite ainda não existe |
| WebSocket não autorizado | Assinar lobby alheio, sessão revogada | handshake autenticado, autorização por lobby, heartbeat/revalidação | entrega local; sem Redis/fan-out |
| Vazamento em logs | Tokens, telefone, query string, corpo | logs sem query string/corpo; request ID; revisão de eventos | revisão contínua necessária |
| Push token exposto | Token em resposta/log de outro usuário | token privado, único, revogável, sem listagem pública | provedor real ainda não configurado |
| Outbox duplicada/perdida | Evento entregue duas vezes ou parado | gravação transacional, status, idempotência do consumidor | dispatcher/push real pendente |
| Backup indisponível/corrompido | Perda de dados locais | `pg_dump`/`pg_restore` documentados e testados | produção exige storage externo, criptografia e RPO/RTO |
| Dependência vulnerável | Biblioteca com CVE | versões fixadas, CI, revisão de lockfile | auditoria automatizada de CVE ainda pendente |
| Enumeração de usuários | Buscar usuários/perfis livremente | sem endpoint global de busca; dados sociais limitados às relações | ranking expõe nome/divisão; revisar privacidade |
| Abuso de recursos | Payload grande, muitas conexões, carga | limites de tamanho, rate limiting parcial, timeouts | rate limit global e proteção de borda pendentes |
| Acesso cruzado entre organizações (BOLA) | Membro de uma organização lê ou altera membros, estabelecimentos, quadras, fotos, reservas ou financeiro de outra | vínculo obrigatório, capacidade por papel, consulta sempre escopada pela organização, 404 para não-membro e testes BOLA | ACL por quadra não existe; autorização é por organização |
| Upload de imagem maliciosa | Polyglot, malware, decompression bomb, EXIF com localização, arquivo acima do limite | validação real por Pillow, reencode JPEG, remoção de EXIF, limites de bytes/pixels/dimensões, storage privado e serving autorizado | antivírus dedicado e storage de produção pendentes |
| Abuso de revisão de foto | Organização aprovar conteúdo impróprio ou foto com pessoa | revisão por `OWNER`/`ADMIN`, motivo obrigatório na rejeição, auditoria, `OPERATOR` sem revisão | revisão independente e denúncia de foto pendentes |
| Dupla reserva | Dois aceites concorrentes para o mesmo espaço/intervalo | lock da linha do espaço, verificação transacional de holds/reservas, teste PostgreSQL concorrente | exclusão por intervalo no banco ainda não usada; cobertura por serviço; criação concorrente não testada |
| Timer adulterado ou reiniciado | Cliente tentar prorrogar T1/T2/T3 ou agir após o prazo | prazos no backend, timers independentes, rejeição após deadline, worker idempotente | T2 comercial implementado; validar feriados |
| Pagamento simulado exposto | Usar endpoint de simulação em produção | rota só permite ambiente local/teste/development/ci | revisão de configuração de deploy necessária |
| Acesso indevido a reserva | Participante ou organização consultar reserva alheia | autorização por participante/organização em cada rota | testes contínuos a cada novo endpoint |
| Custódia no protótipo | Dinheiro real ficar na conta do JOGA sem segregação patrimonial | modelo B documentado, ledger e repasse em `starts_at + 2h`; CNPJ/contrato/revisão jurídica antes de dinheiro real | risco jurídico/regulatório se operar dinheiro real antes da 14E/19A |
| Ledger não integrado | Obrigação financeira ficar fora do ledger de dupla entrada | ledger novo existe com trigger; fluxos usam ledgers legados | P0: integrar na 14E |
| Preço/taxa não persistidos | Reserva não guardar valor do espaço, taxa e percentual | cálculo existe; persistência pendente | P0: 14E |
| Escrow/conta de terceiro | Uso indevido do saldo ou insolvência | modelo C exigido para escala; B no protótipo com risco declarado | contrato e fornecedor pendentes |
| CPF/NFS-e | Exposição de CPF ou documento fiscal ausente | placeholder; CPF a cifrar; NFS-e por reserva | 14E/19A |
| Troca de PSP sem abstração | Domínio acoplado ao Mercado Pago e difícil migrar no futuro | adaptador de PSP desacoplado; Mercado Pago é o PSP atual e Inter/Pagar.me ficam para o futuro (ADR 0048) | adaptador do Inter não é dependência do protótipo |
| Webhook de pagamento forjado/replay | Confirmar reserva sem pagamento real | assinatura HMAC, consulta server-to-server, `psp_webhook_events` idempotente; segredo e URL HTTPS obrigatórios fora do local | hash do corpo e rollback em falha pendentes |
| Divergência de valor/referência | PSP devolver valor diferente da cobrança | conferência de `amount_cents` e `external_reference` antes de aplicar status | conciliação periódica pertence à Fase 15 |
| Reembolso indevido/duplicado | Cancelar reserva e tentar estornar duas vezes ou reembolsar cobrança não paga | autorização por organização, idempotência por `payment_refunds`, ledger append-only e teste de repetição | reembolso parcial e compra de pacote não tratados |
| Reembolso após repasse | Estornar reserva já concluída/liberada | `VENUE_RELEASE` existe; `REVERSED` não é usado | P0: reverter/bloquear repasse |
| Cobrança dupla Pix + crédito | Pagar a vaga por Pix e depois quitá-la com crédito | — | P0: bloquear quitação se a vaga já estiver paga |
| Perda de crédito no T3 | Expirar reserva sem devolver crédito consumido | — | P0: devolver no T3 |
| Abuso de identidade visual | Foto de terceiro, avatar ofensivo, impersonação | sem fotos de pessoas; avatar de catálogo fechado validado pelo backend; nome/tag moderados; denúncia de perfil | catálogo e critérios de moderação ainda pendentes |
| Sequestro de sessão web | XSS, CSRF ou vazamento de refresh token | refresh em cookie `HttpOnly`/`SameSite=Strict`, access só em memória, CSRF de duplo envio em refresh/logout, CSP estrita no build | `JOGA_WEB_COOKIE_SECURE` sem validação obrigatória no boot; `frame-ancestors`/HSTS na hospedagem; revisão dedicada de XSS pendente |

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
- **Médio:** cabeçalhos de segurança da hospedagem do painel (`frame-ancestors`, HSTS, `Permissions-Policy`) ainda não configurados; `JOGA_WEB_COOKIE_SECURE` não tem validação obrigatória no boot.
- **Médio:** moderação de chat e denúncias têm backend/painel, mas o classificador local e a suspensão permanente não existem.
- **Médio:** catálogo de avatares e moderação de nome/avatar pendentes.
- **Médio:** revisão de foto de quadra ainda é feita pela própria organização; revisão independente e denúncia de foto pendentes.
- **Médio:** storage de fotos é local; provedor de produção, criptografia, backup e limpeza de órfãos não definidos.
- **Médio:** T2 comercial implementado; validar feriados, fusos e fechamentos.
- **Alto:** no protótipo, o pagamento usa o Mercado Pago com jogadores reais; dinheiro real exige CNPJ/MEI, contrato, 14E e revisão jurídica.
- **Alto:** o Mercado Pago centraliza o valor; repasse é ledger/manual no modelo B, sem split e sem escrow C.
- **Alto:** ledger de dupla entrada não integrado e taxa não persistida; correção na 14E.
- **Médio:** webhook do Mercado Pago ainda não foi validado com credenciais reais; testes usam HTTP simulado.
- **Médio:** e-mail do pagador é obrigatório na Orders API e o cadastro atual é por telefone.
- **Baixo:** cobertura de UI mobile e testes em aparelho são manuais.

## Critérios para piloto

1. Restore local reproduzível e documentado.
2. Testes de carga local sem falhas críticas.
3. Nenhuma vulnerabilidade crítica/alta conhecida sem bloqueio explícito.
4. Limites de custo de SMS/mapas/infra definidos.
5. Responsável por incidentes e rollback definidos.
6. LGPD e retenção revisadas antes de dados reais.
