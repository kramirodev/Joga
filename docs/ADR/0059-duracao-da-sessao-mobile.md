# ADR 0059 — Duração da sessão no app mobile

- **Status:** Aprovado para implementação em 2026-11-20, a pedido do responsável.
- **Data:** 2026-11-20
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0013, ADR 0058, `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.4, `backend/app/core/config.py`, `backend/app/modules/identity/sessions.py`.

## Contexto

O produto é exclusivamente mobile e de uso esporádico: o jogador abre o app para marcar ou confirmar uma partida e pode passar dias sem usá-lo. Com os padrões anteriores — refresh absoluto de 30 dias e inatividade de 7 dias — o jogador era deslogado depois de uma semana sem abrir o app, o que foi relatado como logout rápido demais para o uso real.

O desenho vigente (ADR 0013) já oferece o mecanismo correto: access token curto (10 min), refresh opaco rotativo, persistido apenas como HMAC, revogável por sessão/família, com detecção de reuso (ADR 0058). O que estava inadequado era apenas a duração da sessão, não o modelo de segurança.

## Alternativas consideradas

1. **Manter 7 dias de inatividade e 30 dias absolutos.** Simples, porém contraria o uso esporádico do app e o problema relatado; o jogador precisa refazer login (OTP/e-mail/passkey) sem que houvesse evento de segurança.
2. **Access token de longa duração.** Reduziria a necessidade de refresh, mas amplia a janela de uso de um token vazado e não é revogável por requisição sem consulta extra; o access continua curto.
3. **Refresh sem expiração absoluta.** Manteria a sessão para sempre, mas elimina o limite máximo de vida da família e dificulta limitar dano de um refresh comprometido.
4. **30 dias de inatividade e 180 dias absolutos (escolhida).** Cobre folgadamente o uso esporádico (mais de 15 dias de folga) e mantém um teto duro de seis meses, com rotação, revogação e detecção de reuso preservadas.

## Decisão

1. `JOGA_REFRESH_IDLE_TTL_DAYS` passa a ter padrão **30** (mínimo 1, máximo 90). O idle é renovado a cada rotação: a nova sessão recebe `idle_expires_at = instante da rotação + 30 dias`.
2. `JOGA_REFRESH_ABSOLUTE_TTL_DAYS` passa a ter padrão **180** (mínimo 1, máximo 365). A expiração absoluta é herdada da família em toda rotação; não é recalculada a partir da rotação.
3. `JOGA_ACCESS_TOKEN_TTL_SECONDS` permanece **600** (10 min). O app continua renovando o access pelo refresh.
4. A checagem de expiração e a revogação da família permanecem como estão: idle ou absoluto vencidos recusam a rotação (`InvalidRefreshToken`), reuso de token rotacionado segue a ADR 0058, e logout, troca de credencial e revogação de dispositivo continuam encerrando a sessão.
5. Não há migração: `sessions.expires_at` (absoluto) e `sessions.idle_expires_at` já existem e são preenchidos pelo serviço. A mudança é só de configuração e vale para sessões emitidas/rotacionadas a partir do novo boot; sessões antigas mantêm os prazos já gravados.

## Consequências

- O jogador permanece logado por até 30 dias sem abrir o app e por até 180 dias de uso contínuo, sem novo OTP/e-mail/passkey.
- A superfície de um refresh comprometido dura mais tempo. Mitigações preservadas: token opaco armazenado só como hash no servidor, rotação a cada uso, detecção de reuso com revogação da família, logout remoto por dispositivo e revogação global.
- O refresh token no dispositivo fica mais tempo no Keychain/Keystore; o app deve manter o armazenamento seguro e nunca registrar o token em log.
- O cookie de refresh do painel web acompanha o absolute (180 dias) via `max_age`, mas o painel continua usando o mesmo fluxo de revogação.
- Ajustar os prazos segue sendo operacional, por variável de ambiente, sem nova decisão para valores dentro dos limites; valores acima de 180 dias absolutos ou 90 dias de inatividade exigem nova decisão.
