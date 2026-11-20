# ADR 0058 — Janela de tolerância na rotação do refresh

- **Status:** Aprovado para implementação em 2026-11-20, a pedido do responsável.
- **Data:** 2026-11-20
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0013, `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.4, `backend/app/modules/identity/sessions.py`.

## Contexto

A ADR 0013 determina que reutilizar um refresh já rotacionado revoga toda a família. Na prática, duas chamadas concorrentes do mesmo cliente com o mesmo refresh — uma corrida de rede ou de múltiplos processos do app — fazem a chamada perdedora apresentar um token que a vencedora acabou de rotacionar. O resultado é `refresh_reuse_detected` e logout imediato, mesmo sem indício de roubo.

O cliente será corrigido com single-flight, mas o servidor não pode depender disso para não deslogar jogadores legítimos.

## Alternativas consideradas

1. **Manter a revogação incondicional.** Simples, porém transforma qualquer corrida legítima em logout e agrava o problema real relatado.
2. **Devolver o par atual da família na tolerância.** Impossível com o desenho vigente: o servidor persiste apenas HMAC do refresh, não o valor em claro. Emitir um par novo invalidaria a resposta vencedora (o cliente que a recebeu ficaria com um refresh já substituído) e daria sessão nova a um token roubado dentro da janela.
3. **Janela curta de tolerância com `401 refresh_retry_required` (escolhida).** Não revoga, não emite tokens e instrui o cliente a reler o par mais novo entregue pela chamada vencedora e repetir.

## Decisão

1. Ao receber um refresh já substituído, o servidor tolera **somente o token imediatamente anterior ao topo da família**, quando:
   - a substituição ocorreu há menos de `JOGA_REFRESH_REUSE_GRACE_SECONDS` (padrão **30 s**, mínimo 0, máximo 300; `0` desliga);
   - o sucessor existe, não foi rotacionado de novo e não está revogado;
   - a família não tem nenhum registro de reuso suspeito (`revoked_reason = refresh_reuse`).
2. Na tolerância, a família **não** é revogada e a resposta é `401 {"detail":{"code":"refresh_retry_required"}}` (mobile) ou o mesmo código no refresh web. Nenhum token é devolvido.
3. Fora da janela, reutilizando token mais antigo, ou com a família já revogada, mantém-se o comportamento anterior: revogar a família e responder `401 refresh_reuse_detected`.
4. Toda tolerância registra o evento de segurança `auth.refresh_grace_used`, com `user_id` e `age_seconds`. Nenhum token, hash ou telefone entra no evento.
5. A idade usa `sessions.revoked_at`, já existente; não há migração. O instante da operação é capturado **depois** do `SELECT ... FOR UPDATE`, para que a chamada perdedora da corrida não calcule uma idade negativa. Desvio pequeno de relógio entre instâncias (rotação aparentemente no futuro) é tratado como idade zero; desvio maior que a janela falha fechado.

## Consequências

- Corridas legítimas deixam de causar logout; o cliente precisa tratar `refresh_retry_required` como transitório, nunca como sessão encerrada.
- A detecção de roubo continua valendo para replay fora da janela ou de tokens mais antigos; a tolerância não emite credenciais, então não amplia o poder de um token roubado.
- O cliente é responsável por reler o armazenamento seguro após a resposta vencedora; um cliente que só tenha o token antigo não consegue se recuperar sozinho.
- Ajustar a janela é operacional, por variável de ambiente; valores acima de 300 s exigem nova decisão.
