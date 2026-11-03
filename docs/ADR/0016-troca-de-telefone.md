# ADR 0016 — Troca de telefone autenticada

- **Status:** Aprovado para o MVP em 2026-11-03, a pedido do responsável ao autorizar a continuidade da Fase 3. Requer ratificação para produção.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0013 (sessões), ADR 0015 (recibo de verificação), `docs/DATA_MODEL.md`.

## Contexto

O telefone é o contato verificado da conta, mas pode ser trocado, reciclado ou comprometido. A Fase 3 exige troca de telefone e recuperação segura. A recuperação depende de um segundo fator forte (passkey) e será tratada depois; a troca de telefone pode ser implementada com a sessão autenticada atual + OTP no novo número.

## Decisão

1. A troca de telefone exige **sessão autenticada**; não é um fluxo público.
2. `POST /api/v1/auth/phone-change/challenges` recebe o novo telefone, recusa número igual ao atual e número já vinculado a outra conta ativa, e envia OTP com finalidade `phone_change` vinculado ao `user_id`.
3. `POST /api/v1/auth/phone-change` recebe `challenge_id` + código, confere que o desafio pertence ao usuário autenticado e tem a finalidade correta, valida o OTP e só então altera o telefone.
4. Na confirmação:
   - o telefone antigo é marcado como liberado (`released_at`) e deixa de ser primário;
   - o novo telefone é gravado como verificado e primário;
   - o recibo é marcado como usado;
   - **todas as sessões do usuário são revogadas**, inclusive a atual, forçando novo login com o novo número.
5. Erros são genéricos para desafio/código inválido (`400 invalid_phone_change`); telefone já usado retorna `409 phone_already_registered`; telefone igual retorna `400 phone_unchanged`.
6. Eventos de segurança registram solicitação, falha e conclusão sem telefone em claro.

## Alternativas consideradas

1. **Trocar o telefone sem revogar sessões.** Rejeitado: uma sessão antiga poderia continuar válida após uma alteração de contato sensível.
2. **Confirmar a troca no endpoint público de verificação.** Rejeitado: permitiria que qualquer portador do `challenge_id` consumisse o desafio de outro usuário.
3. **Trocar o telefone apenas com senha/OTP no número antigo.** Rejeitado no MVP: o número antigo pode estar comprometido; a sessão atual + OTP no novo número é o mínimo viável.
4. **Recuperação usando apenas SMS.** Rejeitado pelo `AGENTS.md`; recuperação exigirá passkey ou outro fator forte.

## Consequências

- O usuário precisa estar autenticado e ter acesso ao novo número.
- A revogação de todas as sessões aumenta a segurança, mas exige novo login imediatamente após a troca.
- A operação é auditável e idempotente por recibo; repetir a confirmação falha.
- Recuperação de conta continua pendente e não pode depender apenas de SMS.
