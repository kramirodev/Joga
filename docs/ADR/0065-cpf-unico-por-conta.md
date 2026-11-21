# ADR 0065 — CPF único por conta (hash com índice único)

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md`,
  `docs/JOGA_DOCUMENTACAO_TECNICA.md`, `docs/ADR/0049-modelo-tributario-da-intermediacao.md`,
  `backend/app/modules/profile/cpf.py`,
  `backend/app/modules/profile/models.py`,
  `backend/app/modules/profile/service.py`,
  `backend/app/modules/organizations/verification.py`,
  `backend/migrations/versions/7a1b2c3d4e5f_cpf_unique_hash.py`.

## Contexto

O CPF do jogador já era gravado cifrado com AES-256-GCM (ADR 0049 §9.3), mas não
havia unicidade. A mesma pessoa podia criar várias contas e informar o mesmo CPF
em todas, o que enfraquece Trust Factor, punições, limites promocionais e a
própria noção de conta.

A decisão do dono é direta: **um CPF = uma conta**. A solução não pode expor o
CPF nem permitir consulta por CPF a partir de respostas, logs ou painel.

## Decisão

### 1. Coluna de hash

`user_profiles` passa a ter `cpf_hash CHAR(64)` (hex de HMAC-SHA256), anulável:

| Situação | `cpf_ciphertext` | `cpf_hash` |
| --- | --- | --- |
| Conta sem CPF | `NULL` | `NULL` |
| Conta com CPF | preenchido | preenchido |

A constraint `cpf_present_consistent` foi ampliada para exigir hash quando há
ciphertext e proibir hash quando não há. O índice
`uq_user_profiles_cpf_hash` é **único e parcial** (`WHERE cpf_hash IS NOT NULL`),
portanto várias contas sem CPF continuam permitidas.

### 2. Derivação

```
cpf_hash = HMAC-SHA256(
  key  = JOGA_PHONE_HASH_SECRET,
  msg  = "cpf:" + CPF normalizado (11 dígitos, sem formatação),
).hexdigest()
```

- Reutiliza um segredo existente, já obrigatório e não-default fora do ambiente
  local (`JOGA_PHONE_HASH_SECRET`), sem criar configuração nova.
- O rótulo `cpf:` separa o domínio do hash de telefone/OTP que usa o mesmo
  segredo; não há reutilização direta de digest.
- **Não** usamos `JOGA_CPF_KEY` como chave do HMAC porque a rotação dessa chave
  (prevista em `JOGA_CPF_PREVIOUS_KEYS`) mudaria todos os hashes e quebraria a
  unicidade histórica. A chave de cifra continua rotacionável sem tocar no hash.
- Rotacionar `JOGA_PHONE_HASH_SECRET` exigirá um backfill coordenado de
  `cpf_hash`; isso é aceito porque esse segredo é estável por natureza.

### 3. Migração e backfill

A revisão `7a1b2c3d4e5f` (após `6f1a2b3c4d5e`):

1. adiciona a coluna;
2. decifra cada CPF existente em memória com o `cpf_key_id` da linha;
3. calcula o HMAC e atualiza `cpf_hash`;
4. recria a constraint `cpf_present_consistent`;
5. cria o índice único parcial.

Se dois registros tiverem o mesmo CPF, a migração **falha** antes de gravar
qualquer hash e informa apenas os `user_id` envolvidos. O sistema não escolhe
vencedor, não apaga conta e não deixa o CPF em log. A resolução é manual
(unificar/remover o CPF de uma das contas) e a migração é reexecutada.

O downgrade remove índice, coluna e restaura a constraint anterior. O ciphertext
permanece intacto em todo o ciclo.

### 4. Contrato da aplicação

Todo caminho que grava CPF calcula e grava `cpf_hash` na mesma transação:

- `PUT /api/v1/me/cpf` (perfil);
- `_persist_cpf_if_absent` na verificação de CNPJ de organização, quando o
  perfil ainda não tinha CPF.

CPF já pertencente a outra conta responde:

```
HTTP/1.1 409 Conflict
{"detail": {"code": "cpf_already_registered"}}
```

O mesmo código é usado no cadastro de organização. A checagem prévia dá a
mensagem estável; o índice único é a defesa contra corrida. CPF nulo ou removido
por `DELETE /api/v1/me/cpf` libera a conta para outro CPF, mas nunca duplica um
CPF ativo.

### 5. Privacidade

- `cpf_hash` não entra em schema de resposta, `ProfileResponse`, painel admin,
  auditoria ou log.
- Auditoria continua registrando apenas `cpf_present: true/false`.
- Mensagens de erro e da migração nunca contêm CPF nem hash.
- A máscara `***.***.***-NN` continua sendo a única exposição permitida.
- O hash é *blinded*: sem o segredo, o espaço de CPFs (~10^9) não pode ser
  enumerado offline a partir do banco.

### 6. Testes

- cadastro do CPF A, nova tentativa em outra conta → 409;
- CPF B em outra conta → 200;
- atualização de perfil para CPF já usado → 409 e valor anterior preservado;
- duas contas sem CPF convivem (índice parcial + constraint);
- índice rejeita hash duplicado diretamente no banco;
- payloads, logs e auditoria sem CPF nem hash;
- migração com registro cifrado faz backfill correto;
- migração com CPF duplicado aborta sem alterar contas;
- `upgrade` / `downgrade -1` / `upgrade` no PostgreSQL real.

## Consequências

- Uma conta nova com CPF já usado é recusada mesmo que o telefone/e-mail sejam
  diferentes. Isso é intencional.
- A recuperação de uma conta existente deve usar os fluxos de login/recuperação,
  não a criação de outra conta.
- O painel pode continuar exibindo apenas a máscara; não há busca por CPF.
- A operação precisa manter `JOGA_PHONE_HASH_SECRET` estável e guardado no
  secret manager fora do ambiente local.

## Fora do escopo

- Bloqueio automático de contas que compartilham CPF (aqui a segunda é recusada;
  não há investigação de fraude).
- Consulta à Receita para validar titularidade do CPF.
- Unificação automática de contas duplicadas já existentes: a migração apenas
  falha e exige decisão humana.
- Busca administrativa por CPF ou exportação do hash.
- Biometria, documento com foto ou prova de vida.
