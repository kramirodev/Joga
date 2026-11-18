# CPF, base legal e retenção

**Versão:** 1.0<br>
**Data:** 17 de novembro de 2026<br>
**Fase:** 14E-E (conformidade) da ADR 0049.<br>
**Natureza:** descrição do que o código faz hoje. Não é parecer jurídico; os pontos marcados como pendentes dependem de revisão profissional.

> Regra de leitura: este documento descreve o tratamento técnico do CPF no backend.
> Política de privacidade publicada, prazos definitivos de guarda e fluxo de
> atendimento ao titular ainda dependem de revisão jurídica (Fase 19).

---

## 1. Por que o CPF existe no produto

O CPF é necessário para identificar o **tomador** do documento fiscal da quadra
contra o jogador (ADR 0049 §3.6 e §9.3). Ele não é prova de identidade civil, não
é chave primária e não é usado em matchmaking, rating, reputação ou antifraude
nesta fase.

- Identidade interna: `users.id` (UUID).
- Telefone verificado: contato, não identidade civil.
- CPF: dado fiscal do tomador, coletado apenas quando o jogador informa.

## 2. Base legal e finalidade

| Uso | Base legal pretendida (LGPD art. 7º) | Situação |
|---|---|---|
| Emitir/registrar documento fiscal da quadra contra o tomador | II — cumprimento de obrigação legal ou regulatória; V — execução de contrato | A validar com contador e advogado tributário |
| Comprovar o aceite dos Termos de Uso | V — execução de contrato; II — obrigação legal | A validar com o jurídico |
| Segurança e auditoria de acesso ao dado | IX — legítimo interesse, com minimização | Interno |

Princípios aplicados: finalidade, necessidade, minimização e segurança. O CPF não
é coletado no cadastro; só existe quando o jogador o envia explicitamente.

## 3. Onde o CPF fica

| Local | Conteúdo | Observação |
|---|---|---|
| `user_profiles.cpf_ciphertext` | `nonce(12) ‖ ciphertext ‖ tag(16)` | AES-256-GCM, AAD = `users.id` (16 bytes) |
| `user_profiles.cpf_key_id` | id da chave usada | Permite rotação sem recifrar tudo |
| `user_profiles.cpf_last2` | dois últimos dígitos | Único dado exibível (`***.***.***-25`) |
| `user_profiles.cpf_updated_at` | instante da última gravação | Sem histórico do valor |
| `fiscal_document_takers.cpf_ciphertext` / `cpf_key_id` | snapshot no instante da intenção fiscal | Um tomador por jogador e reserva |

Não existe cópia em claro no banco. O `CHECK cpf_present_consistent` impede que
`cpf_ciphertext`, `cpf_key_id` e `cpf_last2` fiquem dessincronizados.

## 4. Chave e criptografia

- Algoritmo: AES-256-GCM (`cryptography`), nonce aleatório de 12 bytes por gravação.
- AAD: bytes do `user_id`. Copiar o ciphertext para outro usuário não decifra.
- Chave: 32 bytes em base64, apenas em configuração (`JOGA_CPF_KEY`,
  `JOGA_CPF_KEY_ID`). Nunca no banco, no Git, no bundle mobile ou em log.
- Boot: fora de `local`/`test`/`development`/`ci`, a ausência de chave impede a
  subida da API. Chave com tamanho errado ou o placeholder de 32 bytes zero é
  recusado sempre.
- Rotação: `JOGA_CPF_PREVIOUS_KEYS` mantém chaves antigas **somente para leitura**,
  identificadas pelo `cpf_key_id` gravado. A recifragem em lote ainda não é
  automatizada; a chave antiga não deve ser descartada antes dela.

## 5. Acesso e exposição

| Operação | Regra |
|---|---|
| Ler o próprio CPF | `GET /api/v1/me/cpf` → `cpf_present` + `cpf_masked` |
| Gravar/substituir | `PUT /api/v1/me/cpf`, validação de formato e dígitos |
| Anonimizar | `DELETE /api/v1/me/cpf`, sem alterar o snapshot fiscal |
| Decifrar | Apenas backend, em memória, para finalidade fiscal; não há endpoint |
| Administração | Nenhum endpoint de painel lê ou decifra CPF nesta fase |

- Autorização é por sessão autenticada: o `user_id` vem do token, nunca do corpo
  ou da URL.
- A resposta nunca inclui o CPF completo, o ciphertext ou a chave.
- Erros usam códigos (`invalid_cpf`, `cpf_key_unavailable`) e não ecoam o valor
  recebido.
- Auditoria: `user.cpf_updated` e `user.cpf_deleted` registram apenas
  `{"cpf_present": true|false}`; nenhum dígito, chave ou hash do CPF.
- Logs HTTP não registram corpo de requisição.

## 6. Retenção

| Dado | Prazo proposto | Justificativa |
|---|---|---|
| CPF no perfil (`user_profiles`) | Enquanto a conta existir ou até o jogador remover | Necessário para novas intenções fiscais |
| Snapshot em `fiscal_document_takers` | Pelo prazo de guarda do documento fiscal aplicável | Obrigação legal/fiscal, a confirmar com contador |
| CPF cifrado após `DELETE /me/cpf` | Removido imediatamente do perfil; snapshot anterior preservado | Direito de eliminação não apaga prova fiscal já constituída |
| Termos aceitos (`terms_acceptances`) | Enquanto o contrato puder ser questionado | Prova de aceite; guarda `terms_hash`, `ip_hash` e `user_agent_hash`, nunca IP/UA em claro |

Prazos definitivos (por exemplo, cinco anos fiscais) estão **pendentes de
confirmação** e devem entrar na política de privacidade publicada. Nesta fase, não
há rotina automática de expurgo do snapshot fiscal.

## 7. Direitos do titular no código atual

- **Confirmação e acesso:** `GET /me/cpf` mostra presença e máscara.
- **Correção:** `PUT /me/cpf` substitui o valor; não há histórico em claro.
- **Eliminação:** `DELETE /me/cpf` anonimiza o perfil; o snapshot fiscal permanece
  com base legal própria e é sinalizado na política.
- **Portabilidade e detalhamento do snapshot:** não implementados.

## 8. Riscos e pontos abertos

1. Base legal e prazo de guarda do snapshot fiscal precisam de parecer.
2. Não há fluxo administrativo de acesso ao CPF; quando existir (Fase 19A), precisa
   de autorização, justificativa e auditoria próprias.
3. Recifragem em lote na rotação ainda é manual.
4. O painel web não deve exibir CPF nem permitir busca por CPF; se isso for
   necessário no futuro, exige ADR e controle de acesso específico.
5. Testes usam CPF sintético e chave de teste de 32 bytes; nenhum dado real entra
   no repositório.

## 9. Referências

- `docs/ADR/0049-modelo-tributario-da-intermediacao.md` §3.6 e §9.3.
- `docs/DECISOES_BACKEND_ADR_0049.md`.
- `docs/DATA_MODEL.md` (seções 3 e 6).
- `docs/RUNBOOK.md` (CPF, termos e intenção fiscal).
- `backend/app/modules/profile/cpf.py` e `backend/tests/test_compliance_stage8.py`.
