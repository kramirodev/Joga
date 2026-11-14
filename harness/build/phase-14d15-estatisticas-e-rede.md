# Fase 14D.15 — Estatísticas pessoais e inteligência de rede

**Status:** implementado no backend em 2026-11-13.
**Depende de:** 14D.7 (temporada), Fase 7/8 (resultados e rating), 14D.12 (passe).

## Problema

A ADR 0045 definia o que pode ser lido, mas não existia endpoint de estatística
pessoal, histórico por quadra, passaporte nem painel de rede. Sem isso, o
perfil e a temporada só mostram XP.

## Decisão

1. **Estatística essencial é livre:** partidas, vitórias, empates, derrotas,
   taxa de presença, streak atual e recorde. Nada de MMR bruto, RD ou
   volatilidade.
2. **Presença** é derivada de `checked_in` versus `no_show` em partidas
   finalizadas; não é dado de evento de jogo.
3. **Histórico por quadra e passaporte são do passe.** O histórico agrupa por
   `venue_space` via `booking.lobby_id`; o passaporte soma temporadas, insígnias
   e quadras.
4. **Rede em faixas:** quatro faixas (madrugada, manhã, tarde, noite) no fuso de
   São Paulo. Janela de 30 dias, amostra mínima de 20 partidas por célula.
5. **Célula abaixo do mínimo não aparece.** O total amostral aparece para
   contexto, mas nunca uma célula pequena.
6. **Atualização diária** é representada pela data da leitura; não há tempo real
   nem mapa de pessoas.
7. **Free vê quadras com mais movimento e os próprios horários; passe vê as
   faixas por quadra.** A rede nunca filtra matchmaking.
8. **Painel B2B fica fora desta fatia.**

## Superfície

| Método | Rota | Acesso |
|---|---|---|
| GET | `/api/v1/me/stats` | Livre |
| GET | `/api/v1/me/stats/courts` | Passe |
| GET | `/api/v1/me/stats/passport` | Passe |
| GET | `/api/v1/me/network` | Livre; faixas só no passe |

## Testes

`tests/test_stats.py`: estatística livre sem rating bruto, bloqueio 403 de
quadras/passaporte, histórico e passaporte após o passe, célula de rede oculta
com 19 partidas, visível com 20, faixas apenas para assinante e faixa de pico.

## Pendente

- Gráfico de evolução da divisão (a série já existe em `rating_events`).
- Horários com mais vaga por quadra dependem da agenda de reservas.
- Densidade competitiva por quadra e tendência exigem calibração no piloto.
- Painel B2B, exportação e retenção.
