# ADR 0013 — Sessões e tokens da Fase 3

- **Status:** Aprovado para implementação do MVP em 2026-11-03, a pedido do responsável, com ajuste técnico: access token **opaco** em vez de JWT. Requer ratificação para produção.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_TECNICA.md` §5.4, ADR 0012, ADR 0015, ficha da Fase 3.

## Contexto

A Fase 3 exige sessões revogáveis e refresh rotativo. O documento técnico determina access tokens de curta duração, refresh opacos armazenados no servidor apenas como hash e rotação com revogação da família em caso de reutilização. Falta escolher o formato concreto do access token e os tempos.

## Alternativas consideradas

1. **JWT de acesso curto + refresh opaco.** Não consulta o banco em cada requisição; revogação de access depende da expiração curta; exigiria uma dependência de JWT ou implementação manual.
2. **Access opaco com consulta ao banco (escolhida).** Revogação imediata, sem dependência externa; adiciona uma consulta por requisição e estado de sessão.
3. **Provedor de identidade externo.** Fora do escopo do MVP, adiciona dependência, custo e integração de dados pessoais.
4. **PASETO ou outro formato.** Sem ganho concreto para o monólito atual; aumenta superfície de ferramentas.

## Decisão

1. **Access token:** valor opaco de 32 bytes aleatórios em base64url, com validade inicial de **10 minutos**. O servidor armazena apenas HMAC-SHA256 em `sessions.access_token_hash`; cada requisição autenticada valida o hash, a expiração e a revogação da sessão (uma consulta ao banco), o que permite revogação imediata no MVP. A alternativa JWT foi preterida por exigir uma segunda verificação de revogação e uma dependência adicional sem ganho concreto nesta fase.
2. **Refresh token:** valor opaco de 32 bytes aleatórios em base64url, devolvido uma única vez ao cliente. O servidor armazena apenas HMAC-SHA256 do token, com segredo dedicado.
3. **Rotação:** cada uso do refresh emite um novo par de tokens na mesma família e invalida o anterior. Reutilização de um refresh já rotacionado revoga **toda a família** e registra evento de segurança.
4. **Expiração:** absoluta de **30 dias** e por inatividade de **7 dias**, ambas avaliadas no servidor e registradas na sessão.
5. **Dispositivo:** a sessão referencia `device_id` quando disponível; o refresh é vinculado à sessão e não é aceito por outro dispositivo.
6. **Logout:** encerra a sessão atual (revoga access e refresh) e oferece “sair de todos os dispositivos”, revogando todas as famílias do usuário.
7. **Armazenamento no cliente:** tokens fora de AsyncStorage; usar Keychain/Keystore (decisão de biblioteca no bloco mobile).
8. **Logs:** nunca registrar access token, refresh token, hash de token, OTP ou telefone completo.
9. **Rotação de segredo:** procedimento operacional documentado antes de produção; o MVP aceita um segredo ativo por ambiente.
10. **Segredos separados:** JWT não é usado; access/refresh usam `JOGA_TOKEN_HASH_SECRET`, distinto do segredo de telefone/OTP.

## Consequências

- A revogação é imediata (consulta por requisição), ao custo de uma leitura no banco; pode ser otimizada com cache/Redis quando houver necessidade comprovada.
- Tempos e formato precisam ser validados com testes de rotação, reutilização, revogação e concorrência.
- A decisão final precisa de ratificação para produção.
