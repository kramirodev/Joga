# ADR 0071 — Identidade canônica: tag única e busca `nome#tag`

- **Status:** Aprovado em 2026-11-23 (decisão do dono).
- **Data:** 2026-11-23
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0069 (amizade); `backend/app/modules/identity/tags.py`;
  `backend/app/api/v1/users.py`; `backend/app/core/text.py`.

## Contexto

O nome do jogador era gravado como digitado e não havia como outro jogador
encontrá-lo: a busca de usuário só existia no admin. A “tag” exibida no app era
derivada no cliente de `user_id.slice(0,4)`, sem persistência, sem unicidade e
sem contrato. Isso quebrava o fluxo de amizade — o `POST /friends/requests`
exige `user_id` e o jogador não tinha como descobri-lo.

## Decisões

1. **Tag estável no servidor:** `users.tag`, derivada do UUID, formato `#` + 8
   hexadecimais maiúsculos (`#9F55A2C1`). Em colisão, a tag cresce
   deterministicamente para 10 e 12 hexadecimais; o índice único é a autoridade
   final.
2. **Nome canônico:** `display_name` é gravado com `strip`, espaços repetidos
   colapsados e `upper`, preservando acentos/Unicode e limitado a 60 caracteres.
   A mesma regra vale para cadastro, `PUT /me/profile` e criação admin; a
   migração canoniza os nomes existentes. Nome pode repetir; a tag desambigua.
3. **Busca autenticada:** `GET /api/v1/users/search?q=&limit=20`.
   - `q` de 3 a 40 caracteres;
   - `#TAG` ou `NOME#TAG` buscam a tag exata, sem diferenciar caixa;
   - termo que seja apenas 8/10/12 hex também é tag;
   - caso contrário, `display_name` com `ILIKE` escapado;
   - exclui o próprio usuário, bloqueios nos dois sentidos e contas não ativas;
   - devolve apenas `user_id`, `display_name`, `tag` e `relation`
     (`friend`, `incoming_request`, `outgoing_request`, `none`);
   - limite de 60 consultas por hora por usuário, com 429 e `Retry-After`.
4. **Sem PII:** a busca nunca devolve e-mail, telefone, CPF, status de conta,
   localização ou qualquer outro dado interno.
5. **Perfil:** `GET /me/profile` passa a devolver `tag`; o app deve usar a tag do
   servidor, não a derivação local de 4 caracteres.

## Consequências

- Migração `b7c8d9e0f1a2`: coluna `tag`, backfill determinístico, índice único e
  canonização dos nomes.
- O app mobile precisa consumir `/users/search`, exibir a tag do servidor e
  mapear a `relation` para as ações “Adicionar”, “Enviado”, “Aceitar” e “Amigos”.
- O painel administrativo continua com a busca atual; passa a ver nomes em
  maiúsculas. A tag ainda não aparece no detalhe admin (contrato futuro).
- Duas contas criadas simultaneamente com o mesmo prefixo de 8 hex podem
  disputar o índice único; é um caso raro e fica para o hardening.
