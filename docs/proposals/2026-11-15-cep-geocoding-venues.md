# Proposta: localização de estabelecimento por CEP

- **Status:** Fases 1 e 2 aprovadas e implementadas no backend em 2026-11-15; mapa, provedor pago e backfill pendentes.
- **Data:** 2026-11-15
- **Origem:** auditoria de UI/UX do painel `web/` (JOGA y GESTÃO).
- **Escopo:** backend + contrato HTTP. O painel só consome depois de aprovado.

## 1. Problema

Hoje o cadastro de estabelecimento exige que o vendedor digite latitude e longitude:

- `POST /organizations/{id}/venues` recebe `latitude: float = Field(ge=-90, le=90)` e `longitude` como **obrigatórios** (`backend/app/api/v1/organizations.py:96`).
- O painel, por consequência, expõe dois campos de texto crus (`web/src/pages/organization/VenuesPanel.tsx`).
- O banco aceita nulo: `organization_venues.latitude/longitude` são `nullable=True`, com CHECK apenas de faixa (`backend/app/modules/organizations/models.py:123-145`).

Nenhum vendedor de quadra sabe a latitude do próprio estabelecimento. O resultado prático é coordenada errada, copiada de mapa alheio ou fixada em centro de cidade — o que degrada a busca por proximidade que já existe (`backend/app/modules/venues/discovery.py`, cálculo de distância e ordenação por `distance_km`).

## 2. Objetivo

O vendedor informa **CEP + número** e confirma o ponto no mapa. Coordenadas passam a ser consequência do endereço, não entrada digitada.

Não objetivos desta proposta:

- mudar a busca/descoberta por raio;
- geocodificação no app dos jogadores;
- migração retroativa de estabelecimentos existentes (fica como backfill opcional na fase 2).

## 3. Desenho proposto — Fase 1 (aditiva, sem quebra de contrato)

1. Novo endpoint de consulta: `GET /geo/postal-codes/{postal_code}`.
2. O painel pede o CEP, chama o endpoint, preenche cidade/UF/endereço e recebe coordenadas sugeridas.
3. O painel mostra o pino no mapa; o vendedor ajusta se necessário.
4. O `POST /organizations/{id}/venues` **continua igual**, recebendo `latitude`/`longitude` já resolvidas.

Vantagem: nenhum cliente atual quebra, nenhuma migração é necessária e o time de backend pode entregar o endpoint isoladamente.

## 4. Contrato do endpoint

### Requisição

```
GET /api/v1/geo/postal-codes/{postal_code}?number=1200
```

| Parâmetro | Regra |
|---|---|
| `postal_code` | 8 dígitos; aceitar com ou sem hífen (`20541-004` e `20541004`) |
| `number` | opcional, numérico ou `s/n`; melhora a precisão do geocoding |

Requer autenticação (mesmo `get_current_session` do painel).

### Resposta 200

```json
{
  "postal_code": "20541004",
  "street": "Rua Barão de Mesquita",
  "neighborhood": "Tijuca",
  "city": "Rio de Janeiro",
  "state": "RJ",
  "country": "BR",
  "latitude": -22.9234,
  "longitude": -43.2456,
  "precision": "street",
  "source": "brasilapi",
  "resolved_at": "2026-11-15T12:00:00Z"
}
```

`precision`: `street` (ponto médio do logradouro), `venue` (provedor localizou o estabelecimento), `approximate` (centro do bairro/CEP genérico), `unresolved` (endereço encontrado, coordenada não).

`latitude`/`longitude` podem ser `null` **somente** com `precision: "unresolved"`; nesse caso o painel obriga o pino manual antes de salvar (o `POST` de venue continua exigindo números).

### Erros (padrão `{ "detail": { "code": ... } }` já usado no projeto)

| HTTP | `code` | Quando |
|---|---|---|
| 400 | `invalid_postal_code` | não tem 8 dígitos após normalização |
| 404 | `postal_code_not_found` | provedor de CEP não conhece o CEP |
| 422 | `postal_code_ambiguous` | CEP genérico de grande usuário (caixa postal) sem logradouro único |
| 429 | `rate_limited` | limite por usuário/IP, com header `Retry-After` |
| 502 | `geocoding_provider_error` | provedor de coordenadas falhou |
| 504 | `geocoding_timeout` | provedor excedeu o timeout |

## 5. Regras não funcionais

- **Chave de provedor nunca sai do servidor.** Nada de geocoding chamado pelo painel ou pelo app.
- **Cache obrigatório.** CEP é altamente repetitivo. Guardar por CEP+número com TTL de 30 dias; chave de cache sem dado pessoal.
- **Timeout curto** no provedor (sugestão: 3 s) e `total` de 5 s no endpoint.
- **Rate limit próprio** (ex.: 30 consultas/minuto por usuário) para não estourar a política do provedor.
- **Auditoria**: registrar `source` e `precision` de toda coordenada gravada, para rastrear erro de geocoding sem acusar o vendedor.
- **Validação de faixa** no backend continua obrigatória (`-90..90`, `-180..180`); nunca confiar em coordenada vinda do cliente sem checagem.
- **LGPD**: CEP de estabelecimento é dado comercial, não pessoal. Ainda assim, não registrar CEP junto de IP ou telefone em log de aplicação.

## 6. Fase 2 — persistência (só depois da fase 1 estável)

Colunas novas em `organization_venues`:

| Coluna | Tipo | Regra |
|---|---|---|
| `postal_code` | varchar(8) | opcional, só dígitos |
| `geocoding_source` | varchar(40) | ex.: `viacep+nominatim` |
| `geocoding_precision` | varchar(20) | `street`/`venue`/`approximate`/`manual` |
| `geocoded_at` | timestamptz | quando a coordenada foi resolvida |

Migração Alembic própria; `latitude`/`longitude` continuam `nullable` no banco e obrigatórios na API. Backfill opcional por script, marcando `geocoding_precision = 'manual'` no que já existe.

## 7. Provedores sugeridos

| Etapa | Opção gratuita | Opção paga |
|---|---|---|
| CEP → endereço | ViaCEP ou BrasilAPI (sem chave) | — |
| Endereço → coordenada | Nominatim/OSM (política de ~1 req/s, `User-Agent` identificado) | Google Geocoding ou Mapbox |

Recomendação: começar com ViaCEP + Nominatim em desenvolvimento e orçar Google Geocoding para produção, porque precisão de **número** é o ponto fraco de CEP + Nominatim. Em qualquer cenário, o pino ajustável é a autoridade final.

## 8. Impacto no painel (`web/`)

Depois do endpoint pronto:

1. Substituir os campos `latitude`/`longitude` por `CEP` + `número`, com máscara `00000-000`.
2. Preencher cidade/UF/endereço automaticamente e deixar read-only (editável só por exceção).
3. Exibir mapa com pino arrastável e botão “usar este ponto”.
4. Manter `latitude`/`longitude` no payload atual — nenhuma mudança de contrato no `POST`.
5. Ajustar CSP para o provedor de mapa (tiles/estático) ou usar imagem de mapa servida pelo backend, que evita mexer em `img-src`/`connect-src`.

Enquanto o endpoint não existir, o painel mantém os campos numéricos atuais, com ajuda de texto e validação de faixa — pior UX, mas sem quebra.

## 9. Casos de teste exigidos

- CEP válido com e sem hífen.
- CEP inexistente → 404 sem vazar detalhe do provedor.
- CEP de caixa postal → 422.
- Provedor de coordenadas fora → 502; timeout → 504.
- Cache hit não chama provedor (verificar por contador/log).
- Rate limit por usuário devolve 429 + `Retry-After`.
- `number` ausente ainda devolve `precision: "street"`.
- Resposta nunca inclui chave, token ou URL interna do provedor.

## 10. Critérios de aceite

- Nenhum cliente existente quebra (endpoint novo, `POST` de venue inalterado).
- Vendedor conclui cadastro sem digitar coordenada.
- p95 do endpoint abaixo de 1,5 s com cache quente.
- Coordenada salva sempre com `source` e `precision` registrados.
- Erros seguem o padrão `detail.code` já usado no projeto.

## 11. Riscos

- **Precisão de CEP**: CEP identifica logradouro, não portaria; em shopping, condomínio e galpão o pino cai errado. Mitigação: pino ajustável + `precision` explícita.
- **Dependência de terceiro**: Nominatim tem política de uso e pode bloquear; precisa de plano B.
- **Custo**: Google/Mapbox cobram por requisição; cache agressivo é obrigatório.
- **Dado histórico**: estabelecimentos já cadastrados com coordenada manual podem estar errados; backfill não corrige sozinho.

## 12. Decisões pendentes (para o time de backend)

1. Endpoint fica em `/geo/postal-codes/{cep}` ou dentro de `/venues/resolve-location`?
2. Guardamos `postal_code` no venue já na fase 1 ou só na fase 2?
3. Qual provedor pago será usado em produção e qual o orçamento mensal?
4. O painel pode usar mapa interativo (CSP + dependência nova) ou preferimos mapa estático servido pelo backend?
