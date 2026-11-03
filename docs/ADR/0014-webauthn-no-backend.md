# ADR 0014 — Verificação WebAuthn no backend

- **Status:** Aprovado para implementação do MVP em 2026-11-03, a pedido do responsável ao autorizar a continuidade da Fase 3. Requer ratificação para produção.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.4 e §20, ADR 0011, ficha da Fase 3.

## Contexto

A Fase 1 provou a cerimônia Android com desafio local. Na Fase 3, o backend precisa emitir desafios de uso único e verificar a resposta WebAuthn (RP ID, origem, flags e assinatura) antes de criar sessão. Implementar a verificação criptográfica manualmente é uma fonte de erro de segurança; uma biblioteca mantida reduz esse risco.

## Alternativas consideradas

1. **`py_webauthn` (Duo Labs), versão fixada (proposta).** Biblioteca Python consolidada, cobre registro e autenticação, verificação de origem/RP ID e flags, com API documentada.
2. **`webauthn` (outra implementação Python).** Viável, porém com menor adoção observável; exigiria avaliação equivalente.
3. **Implementação própria.** Rejeitada: aumenta risco de erro em comparação de assinatura, CBOR/attestation e validação de origem, sem ganho de produto.
4. **Delegar a um provedor de identidade.** Fora do escopo e contrário à decisão de manter identidade no backend do JOGA.

## Decisão proposta

1. Adotar o pacote `webauthn` (PyPI, projeto py_webauthn) na versão exata **3.0.1**, fixada em `pyproject.toml` e `requirements.lock`, após revisão de licença e segurança.
2. Configurar explicitamente `RP_ID` e `ORIGIN` por ambiente. Para a prova Android, o RP ID é `joga-passkeys.vercel.app` e a origem esperada é `android:apk-key-hash:<SHA-256 base64url do certificado de debug>`; a origem web, quando existir, é `https://<domínio>`. A lista de origens aceitas é configurável.
3. Desafio gerado pelo servidor com pelo menos 32 bytes aleatórios, armazenado como hash, uso único e validade de **5 minutos**.
4. Registro:
   - exigir `type=public-key`, `challenge`, `origin`, `rpIdHash`, `userPresent` e `userVerified` conforme a política;
   - `attestation: none` no MVP;
   - persistir `credential_id`, chave pública, contador de assinatura, transporte e dispositivo;
   - recusar `credential_id` duplicado.
5. Autenticação:
   - buscar a credencial pelo `credential_id` e recusar credenciais revogadas;
   - verificar assinatura e `rpIdHash` da asserção;
   - atualizar o contador quando aplicável e tratar contador regressivo como sinal de segurança.
6. Múltiplas credenciais por usuário, com nome, data de criação, último uso e revogação individual.
7. Testes com vetores conhecidos, autenticador sintético P-256 e o app Android já validado; iOS continua dependente de AASA/build iOS.
8. Persistir desafios em `passkey_challenges` (usuário opcional, finalidade, expiração curta, uso único e hash do IP). O desafio em si é um nonce público enviado ao cliente; não é segredo, mas nunca deve ser registrado em log.
9. Limitar tentativas/desafios e revogar credenciais individualmente; credenciais revogadas não autenticam.

## Consequências

- A verificação deixa de ser local e passa a proteger o login real.
- A biblioteca e a configuração de RP ID/origem viram superfície crítica; atualizações exigem testes de regressão.
- O bloqueio iOS não impede o backend, mas o critério “Android e iOS” da fase continua aberto.
