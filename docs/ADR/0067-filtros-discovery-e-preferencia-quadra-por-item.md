# ADR 0067 — Filtros reais de discovery e preferência de quadra por item da fila

- **Status:** Aprovado em 2026-11-21.
- **Data:** 2026-11-21
- **Numeração:** esta ADR ocupa o número **0067**, conforme a tarefa. A
  numeração está congelada: **0064** = perfil esportivo a partir da fila,
  **0067** = este contrato.
- **Relaciona:** `docs/ADR/0057-fila-multi-entrada.md`,
  `docs/ADR/0064-perfil-esportivo-a-partir-da-fila.md`,
  `backend/app/api/v1/discovery.py`,
  `backend/app/modules/venues/discovery.py`,
  `backend/app/api/v1/matchmaking.py` e
  `backend/app/modules/matchmaking/service.py`.

## Contexto

Dois fluxos do app dependiam de filtro no cliente, sobre uma página já cortada
pelo servidor:

1. A vitrine `GET /api/v1/discovery/bookable-venues` só aceitava `page`,
   `page_size` e `city`. Filtrar por esporte/formato, cobertura ou distância no
   app olharia apenas os 20 primeiros estabelecimentos: o `total` deixaria de
   corresponder ao filtro e estabelecimentos elegíveis em páginas seguintes
   sumiriam. O card também não dizia quais formatos a quadra aceita.
2. O `PUT /api/v1/matchmaking/queue` aceitava `court_preference` apenas global.
   O jogador que escolhe futebol casual em quadra coberta e vôlei em quadra
   pública precisava de uma preferência só para toda a seleção.

## Decisão — discovery

### Parâmetros

`GET /api/v1/discovery/bookable-venues` passa a aceitar, além de `page`,
`page_size` e `city`:

| Parâmetro | Tipo | Efeito |
|---|---|---|
| `format_id` | UUID | Só estabelecimentos com quadra ativa que aceita o formato. |
| `sport_id` | UUID | Só estabelecimentos com quadra ativa da modalidade. |
| `covered` | booleano | `true`: tem ao menos uma quadra ativa coberta; `false`: não tem nenhuma. |
| `max_distance_km` | inteiro 1–100 | Só estabelecimentos até essa distância do centro da região do usuário. |

- `format_id` e `sport_id` podem ser combinados; se o formato não pertencer à
  modalidade informada, a resposta é `422 format_sport_mismatch`.
- Formato/modalidade inexistente ou inativo responde `422 invalid_format` /
  `422 invalid_sport`.
- `max_distance_km` **exige** `UserRegion` gravada. Sem região, a resposta é
  `422 region_required`. Foi escolhido rejeitar em vez de ignorar o filtro:
  devolver uma lista sem saber a origem daria a falsa impressão de que a
  distância foi aplicada. O app deve pedir/localizar a região e repetir.
- Com `max_distance_km`, estabelecimento sem latitude/longitude é excluído:
  não é possível provar que está dentro do raio.
- `covered=false` significa "nenhuma quadra ativa coberta", não "não filtre por
  cobertura". O app que não quer filtrar deve omitir o parâmetro.

### Card

Cada item de `venues[]` passa a trazer:

```json
{
  "sports": [
    {
      "sport_id": "uuid",
      "sport_name": "Futebol",
      "format_id": "uuid",
      "name": "Futebol 5x5"
    }
  ]
}
```

- A lista contém apenas formatos ativos de modalidades ativas aceitos por
  alguma quadra ativa do estabelecimento.
- O conjunto aceito por uma quadra é a união do `VenueSpace.format_id`
  explícito (quando houver) com os formatos ativos das modalidades vinculadas
  por `VenueSport`. O filtro de formato usa exatamente a mesma união, para todo
  resultado ter um chip correspondente no card.
- Os campos são os mesmos identificadores aceitos nos parâmetros, para o app
  montar o filtro sem inventar nomes nem traduzir slug.

### Ordenação, total e custo

- Todos os filtros são aplicados **antes** da paginação. `total` é a contagem
  de estabelecimentos elegíveis para o filtro completo; a página é um recorte
  desse conjunto. O filtro nunca é aplicado sobre a página.
- A ordenação continua por distância (quando há região), depois nome e id.
- A listagem carrega candidatos e, somente para a página já cortada, quadras,
  agenda, formatos, ingressos e primeira foto em consultas em lote. Não há
  consulta por quadra/modalidade/formato dentro do laço de estabelecimentos.
- A distância é calculada no backend com a região gravada. O cliente não envia
  coordenada por requisição.

## Decisão — preferência de quadra por item

`PUT /api/v1/matchmaking/queue` aceita `court_preference` dentro de cada item de
`selections[]`:

```json
{
  "selections": [
    {
      "format_id": "uuid-futebol",
      "mode": "casual",
      "court_preference": "PRIVATE_ONLY"
    },
    {
      "format_id": "uuid-volei",
      "mode": "ranked",
      "court_preference": "PUBLIC_ONLY"
    }
  ]
}
```

1. **Item vence o global.** A preferência efetiva do par é a do item quando
   presente; sem item, vale o `court_preference` global legado; sem nenhum dos
   dois, a preferência existente é preservada (entrada nova usa a do perfil).
2. **Persistência no perfil.** A preferência efetiva de cada formato é gravada
   no `UserSportProfile` daquele formato, na mesma transação da fila, pelo
   upsert da ADR 0064. Formato sem preferência efetiva não tem o perfil
   alterado. Se o mesmo formato aparecer em mais de um par com valores
   diferentes, o perfil grava o último par na ordem de `selections[]`; cada
   `QueueEntry` mantém a preferência do seu próprio par.
3. **Entrada da fila.** `QueueEntry.court_preference` recebe a preferência
   efetiva do par, inclusive em entrada preservada pelo diff (sem reiniciar
   `created_at`). `GET /queue` já devolve esse campo por entrada, então o app lê
   a preferência efetiva sem recalcular.
4. **Ranqueada aceita preferência.** O item vale para `casual` e `ranked`. A
   restrição de nível em ranqueada não muda: `court_preference` não é nível e
   não participa do pareamento por MMR.
5. **Formato legado.** `formats × modes` + `court_preference` global continua
   funcionando: o global vale para todos os pares, sem item.
6. **Validação.** Valor fora de `PUBLIC_ONLY`, `PRIVATE_ONLY` ou `ANY` responde
   `422 invalid_court_preference`, tanto no global quanto no item, antes de
   qualquer escrita. Global e item juntos são permitidos; o item vence.
7. **Sem migração.** `user_sport_profiles.court_preference` e
   `queue_entries.court_preference` já existem com as constraints necessárias.

## Consequências

- O app pode oferecer filtros de esporte/formato, cobertura e distância
  confiando em `total` e na paginação do servidor.
- O card passa a ser a fonte dos formatos filtráveis; não é necessário manter
  uma cópia local do catálogo para montar os chips.
- A vitrine fica mais pesada por página (mais dados agregados), mas deixa de
  fazer N+1 e passa a filtrar o conjunto inteiro.
- A preferência de quadra deixa de ser uma só por seleção e passa a refletir a
  escolha de cada par, com o perfil do formato coerente para a próxima
  requisição.
- `docs/CONTRATO_RESERVAS_APP.md` §23 ainda descreve apenas o global; a próxima
  atualização do contrato do app deve incorporar o item e os novos parâmetros de
  discovery. Esta ADR é a referência enquanto aquele documento não for revisto.

## Alternativas consideradas

- **Filtrar no app sobre a página:** rejeitado. `total` mentiria e resultados
  elegíveis sumiriam nas páginas seguintes.
- **Ignorar `max_distance_km` sem região:** rejeitado. O app acreditaria que o
  raio foi aplicado. `422 region_required` obriga o fluxo correto.
- **Incluir estabelecimento sem coordenada no filtro de distância:** rejeitado.
  Não há como provar que atende ao raio.
- **`covered=false` como "sem filtro":** rejeitado. O parâmetro booleano deve
  ter semântica simétrica; omitir é o jeito de não filtrar.
- **Preferência por item só na entrada, sem perfil:** rejeitado. A próxima
  seleção perderia a escolha e a ADR 0064 já define o perfil como última
  preferência do formato.
- **Rejeitar global + item:** rejeitado. O global é compatibilidade; o item é
  a escolha mais específica e deve vencer sem quebrar o app antigo.

## Verificação

Testes em `backend/tests/test_discovery_api.py` cobrem: card com `sports`;
filtro por formato e por modalidade; filtro aplicado antes da paginação com
`total` coerente em duas páginas; cobertura `true`/`false`; distância com e sem
região; estabelecimento sem coordenada; combinação de formato + cobertura +
distância; e `422` para distância fora de 1–100, booleano inválido, UUID
inválido, formato/modalidade inexistente e formato de outra modalidade.

Testes em `backend/tests/test_matchmaking_api.py` cobrem: preferência por item
em casual e ranqueada; item vencendo o global; somente global valendo para
todos os pares; perfil de cada formato atualizado; `GET /queue` devolvendo a
preferência efetiva; e `422 invalid_court_preference` sem criar entrada nem
alterar perfil.
