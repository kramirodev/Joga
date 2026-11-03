# ADR 0015 — Recibo de verificação de telefone

- **Status:** Aprovado para o MVP em 2026-11-03, a pedido do responsável ao concluir a Fase 3. Requer ratificação para produção.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0013 (sessões e tokens), ficha da Fase 3, `docs/DATA_MODEL.md`.

## Contexto

A verificação de OTP precisa produzir um artefato que o próximo passo do cadastro/login possa consumir. Sem isso, o endpoint de verificação não tem utilidade: a única prova de que o telefone foi verificado fica no estado interno do desafio, sem um identificador devolvido ao cliente.

Não é desejável criar uma sessão completa neste momento: o ADR 0013 ainda não foi aprovado e o fluxo de conta (criação de usuário, passkey e sessão) pertence ao restante da Fase 3.

## Alternativas consideradas

1. **Não devolver nada e refazer a verificação no próximo passo.** Rejeitado: duplica custo/atrito e permite confusão sobre qual desafio foi validado.
2. **Emitir um JWT de verificação.** Viável, mas mistura o formato de tokens de sessão (ADR 0013) com um artefato de curta duração e aumenta a superfície.
3. **Criar uma tabela dedicada de recibos com token opaco.** Mais isolamento, porém adiciona schema e complexidade antes de existir o fluxo de conta.
4. **Usar o próprio desafio consumido como recibo (proposta).** O `challenge_id` já é um UUID aleatório, de uso único, mantido no servidor e com `consumed_at`. O endpoint devolve o ID, `verified_at` e `receipt_expires_at`; o próximo passo consulta o registro e verifica a janela.

## Decisão proposta

1. O recibo é o `phone_challenges.id` consumido por uma verificação bem-sucedida.
2. A resposta de `POST /api/v1/auth/phone/challenges/{id}/verify` inclui `challenge_id`, `purpose`, `verified_at` e `receipt_expires_at`.
3. A validade do recibo é configurável (`JOGA_OTP_RECEIPT_TTL_SECONDS`, padrão **600 s**) e contada a partir de `consumed_at`.
4. O fluxo de conta/sessão deve:
   - exigir `consumed_at` preenchido e `receipt_expires_at` no futuro;
   - conferir a `purpose` esperada;
   - consumir o recibo uma única vez (marcar como usado no fluxo de conta, sem reutilizá-lo para outra conta).
5. O recibo **não** é access token, refresh token ou prova de identidade civil. Não deve ser registrado em logs nem usado entre dispositivos.
6. O endpoint de verificação registra evento de segurança sem telefone/OTP e responde erro genérico para desafio inválido, expirado ou bloqueado.

## Consequências

- O fluxo de cadastro/login pode avançar para a próxima iteração sem antecipar o formato final de sessão.
- A janela curta limita o impacto de vazamento do `challenge_id`, mas exige que o próximo passo seja rápido.
- O servidor precisa armazenar e consultar o desafio até o consumo; a política de retenção/limpeza deve preservar o recibo pelo menos até a expiração.
- Se o fluxo de conta não consumir o recibo, ele permanece válido até o TTL; o próximo passo deve ser idempotente e marcar o consumo.
- Esta decisão precisa ser ratificada antes de produção ou substituída pelo modelo de sessão do ADR 0013.
