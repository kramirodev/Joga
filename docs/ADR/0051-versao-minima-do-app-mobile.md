# ADR 0051 — Versão mínima do app mobile e bloqueio 426

- **Status:** Aprovado para o ambiente de demonstração em 2026-11-19.
- **Data:** 2026-11-19
- **Relaciona:** ADR 0050 (credencial de login por e-mail), `AGENTS.md` §3/§4/§5,
  `docs/JOGA_DOCUMENTACAO_TECNICA.md` §19.2 e `docs/DEPLOY_DEMO.md`.

## Contexto

O app mobile é distribuído fora de loja durante o beta. Uma atualização pode
ficar pendente por tempo indeterminado, e o backend atual não recebe a versão
do cliente. Assim, um binário antigo continua chamando `/api/v1` e pode:

- consumir cotas de e-mail, rate limits e recursos caros;
- usar fluxos que já foram substituídos (por exemplo, login por telefone);
- apresentar UI incompatível com campos ou regras novas;
- permanecer vulnerável sem que o servidor consiga exigir a correção.

O bloqueio precisa ser **server-side**, não apenas uma tela do app, e não pode
quebrar o painel web, health checks, curl de operação ou o próprio endpoint de
configuração.

## Decisão

### 1. Contrato de identificação

O app mobile envia em todas as requisições REST e no handshake WebSocket:

```text
X-Client: mobile
X-App-Version: MAJOR.MINOR.PATCH
X-Build-Number: <opcional>
X-Platform: android|ios
```

O painel web envia `X-Client: web` e `X-App-Version` do bundle. Health,
`/api/v1/app-config` e caminhos fora de `/api/v1/` não exigem identificação.

### 2. Endpoint de configuração

`GET /api/v1/app-config` é aberto e devolve:

```json
{
  "min_supported_version": "1.0.1",
  "latest_version": "1.0.1",
  "update_url": null,
  "version_gate_enabled": true,
  "update_required": false
}
```

O app consulta antes do login para mostrar a tela de atualização; o `426`
continua sendo a garantia server-side.

### 3. Bloqueio

Com `JOGA_APP_VERSION_GATE_ENABLED=true`:

- mobile com versão ausente, inválida ou menor que `JOGA_MIN_APP_VERSION`
  recebe **426 `app_update_required`**, com versão mínima, última versão e
  `update_url` no `detail`;
- WebSocket mobile antigo fecha com **4403**;
- `X-Client: web` passa (o painel é atualizado junto com o backend);
- sem `X-Client`, User-Agent OkHttp/CFNetwork/Expo é tratado como mobile
  antigo; navegador, curl e clientes de operação continuam liberados;
- `X-Client` desconhecido recebe **426 `unsupported_client`**.

### 4. Configuração

```text
JOGA_APP_VERSION_GATE_ENABLED=true
JOGA_MIN_APP_VERSION=1.0.1
JOGA_LATEST_APP_VERSION=1.0.1
JOGA_APP_UPDATE_URL=            # opcional, HTTPS quando existir
```

O padrão local/teste é desativado. O demo ativa o gate quando houver build
1.0.1 disponível. O app 1.0.0 antigo é bloqueado por não enviar os headers.

## Consequências

- Binários antigos deixam de consumir a API e o WebSocket.
- O app 1.0.1 precisa ser gerado e distribuído antes de ativar o gate; o 1.0.0
  passa a mostrar erro/atualização obrigatória.
- O gate **não é fronteira de segurança**: headers podem ser falsificados. A
  autorização, o rate limiting, a integridade de partidas/rating e a validação
  de entrada continuam no servidor.
- O painel web não é bloqueado; um bundle antigo em cache continua aceito pelo
  fallback de navegador.
- Se um gate for mal configurado, a flag desativa o bloqueio sem reverter o
  código.
- Evolução futura: atestação de app (Play Integrity/App Attest) se houver
  necessidade de provar que o binário é genuíno, o que exige decisão e custo
  próprios.

## Alternativas consideradas

- **Só tela de atualização no app:** não impede abuso por binário antigo.
- **Bloquear todo cliente sem versão:** quebraria painel, curl e operações.
- **`/api/v2` imediato:** não resolve binários antigos que continuam em `/v1`;
  o gate é complementar à versão de contrato.
