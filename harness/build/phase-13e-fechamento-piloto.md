# Fase 13E — Fechamento operacional do piloto

**Status:** implementado no backend e no painel em 2026-11-14.
**Depende de:** 13A/13C (reservas), 9D (notificações), 12A (agenda), 14D.2 (payout).
**Não inclui:** provedor APNs/FCM, lembretes automáticos de todos os timers, PSP real ou política de pausa/reembolso.

## Problema

O piloto ainda tinha três lacunas operacionais: T2 contava em tempo corrido,
o app precisava escolher manualmente a quadra e as notificações ficavam
persistidas sem entrega de push.

## Decisões

1. O estabelecimento pode cadastrar expediente semanal e fechamentos
   excepcionais.
2. O T2 usa minutos úteis dentro do expediente, com teto em tempo corrido de
   `JOGA_BOOKING_T2_MAX_MINUTES`.
3. Sem expediente cadastrado, o cálculo cai para tempo corrido — compatível com
   estabelecimentos antigos.
4. `POST /bookings/from-lobby` escolhe automaticamente uma quadra ativa,
   compatível com o formato, dentro do raio do lobby, com payout pronto e sem
   conflito de agenda.
5. A escolha ordena por distância e depois por preço; a criação explícita
   continua disponível.
6. O painel permite cadastrar expediente e fechamentos e mostra a faixa da
   janela.
7. A Outbox de `notification.created` ganhou dispatcher opcional por webhook.
   Sem `JOGA_PUSH_WEBHOOK_URL`, a Outbox é preservada.
8. O dispatcher não é provedor APNs/FCM; é uma ponte substituível. A central
   persistida continua sendo a fonte de verdade.

## Superfície

| Método | Rota | Efeito |
|---|---|---|
| GET/POST | `/organizations/{org}/venues/{venue}/business-hours` | Expediente semanal |
| DELETE | `/organizations/{org}/venues/{venue}/business-hours/{id}` | Remove expediente |
| GET/POST | `/organizations/{org}/venues/{venue}/closures` | Fechamentos/feriados |
| DELETE | `/organizations/{org}/venues/{venue}/closures/{id}` | Remove fechamento |
| POST | `/api/v1/bookings/from-lobby` | Reserva automática a partir do lobby |

## Modelo

Migração `e1f2a3b4c5d6`:

- `venue_business_hours` (dia, abre, fecha);
- `venue_closures` (intervalo e motivo).

## Operação

```powershell
cd backend
.venv\Scripts\python.exe -m scripts.dispatch_notifications
.venv\Scripts\python.exe -m scripts.dispatch_notifications --loop --interval 30
```

Variável opcional:

```text
JOGA_PUSH_WEBHOOK_URL=https://seu-worker/push
```

## Testes

- `tests/test_business_hours.py`: minutos úteis, fechamento, teto de tempo
  corrido, fallback sem expediente, reserva automática e autorização negativa.
- `tests/test_notifications.py`: dispatcher, push e marcação da Outbox.
- Painel: 20 testes, typecheck, lint, formatação e build verdes.

## Pendente

1. Provedor real APNs/FCM e worker externo de push.
2. Lembretes automáticos de T1/T2/T3/T4 e check-in.
3. Pausa do estabelecimento com reserva confirmada.
4. Política de reembolso de pacote/passe.
5. PSP/Inter, KYC e repasse real.
6. Teste E2E com app, API e painel.
