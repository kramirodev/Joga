# Telas desativadas — compra de ingressos

**Data:** 19 de novembro de 2026<br>
**Flag:** `JOGA_TICKET_PURCHASE_ENABLED`<br>
**Padrão:** `false` (compra de ingressos desligada)<br>
**Motivo:** pagamentos reais, custódia, KYC e NFS-e ainda não estão homologados para o beta. A demonstração pode exibir saldo, extrato, lotes e passe, mas não deve abrir checkout de ingressos nem criar cobrança de pacote.

## 1. Escopo

A desativação cobre apenas a **compra de ingressos**: pacotes e ingresso avulso, com o checkout Pix correspondente. O **passe não está desativado**: a tela de planos e o checkout do passe continuam acessíveis.

No backend, a flag é aplicada por `require_ticket_purchase_enabled` (`backend/app/api/v1/auth_guards.py`). Com `false`, os endpoints de criação, sincronização e confirmação de compra de ingressos respondem `503 ticket_purchase_disabled`; a leitura da carteira, lotes, extrato, pacotes e a compra do passe seguem o fluxo próprio.

## 2. Rotas bloqueadas

| Rota | Tela | Entrada no app | Como reativar |
|---|---|---|---|
| `store` | Loja de pacotes | Nenhuma; deep link mostra a mensagem de compra indisponível | Restaurar uma entrada para `store` e remover a rota de `PURCHASE_ROUTES` |
| `checkout-package` | Checkout de pacote | Nenhuma; deep link mostra a mensagem de compra indisponível | Restaurar uma entrada e remover a rota de `PURCHASE_ROUTES` |
| `buy-3` | Checkout avulso | Nenhuma; permanece `hidden` e o deep link mostra a mensagem de compra indisponível | Manter `hidden` até a compra avulsa ser reativada |

O passe e a rota `checkout-pass` **não estão bloqueados**. `insufficient-tickets` também não é interceptada pela tela genérica; ela permanece registrada e exibe a mensagem própria de ingressos insuficientes.

## 3. Mensagens oficiais

### Compra de ingressos indisponível

Usada em `store`, `checkout-package`, `buy-3` e deep links de compra de ingressos.

- **Título:** Compra de ingressos indisponível
- **Corpo:** A compra de ingressos está desativada nesta versão do JOGA. Seus ingressos atuais continuam válidos e podem ser usados normalmente nas reservas.
- **Botão:** Voltar

### Ingressos insuficientes

Usada pela tela `insufficient-tickets`.

- **Título:** Ingressos insuficientes
- **Corpo:** Você precisa de {necessários} ingressos e tem {disponíveis}. A compra de ingressos está desativada nesta versão do JOGA.
- **Botão:** Voltar

A tela aceita os parâmetros de deep link `needed` (ou `required`/`tickets`) e `available`. Sem parâmetro, `disponíveis` vem do saldo da carteira e `necessários` usa o valor informado ou o saldo atual mais um.

### Erro `503 ticket_purchase_disabled`

Qualquer endpoint de compra de ingressos que responda `503 ticket_purchase_disabled` exibe exatamente a mensagem de **Compra de ingressos indisponível**. Código, status HTTP e detalhe interno não aparecem para o jogador.

## 4. O que permanece ativo

- **Carteira e extrato:** `wallet` e `wallet-breakdown` continuam exibindo saldo, movimentações e lotes provenientes do servidor.
- **Lotes e validade:** `LotList` continua mostrando os lotes ativos e suas validades.
- **Passe:** tela de planos, checkout do passe, gestão da assinatura e histórico de franquias continuam ativos.
- **Clãs:** telas de clã, membros, ranking e escudo continuam ativas.
- **Chat:** chat de lobby e de clã continuam ativos, com moderação de texto.
- **Amigos:** lista, convites, bloqueio e denúncia continuam ativos.
- **Moderação:** denúncia de perfil, recursos e ações de moderação continuam ativas.
- **Reservas:** descoberta, solicitação, bloqueio, presença e histórico de reservas continuam ativos; o consumo de ingressos existentes não é afetado.

## 5. Reativação

Para reativar a compra de ingressos, definir `JOGA_TICKET_PURCHASE_ENABLED=true` no ambiente do backend, restaurar as entradas de `store`/`checkout-package`, remover as rotas correspondentes de `PURCHASE_ROUTES` e gerar um novo build. O passe continua com o fluxo independente.

## 6. Estado do código

O selo `COMPRAR` e os botões de compra de ingressos da carteira foram removidos. As rotas `store`, `checkout-package` e `buy-3` continuam registradas, mas não têm entrada no app e são interceptadas pela mensagem oficial de compra indisponível. O servidor continua sendo a barreira efetiva: com `JOGA_TICKET_PURCHASE_ENABLED=false`, qualquer tentativa de compra recebe `503 ticket_purchase_disabled`.
