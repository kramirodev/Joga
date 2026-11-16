# UI mobile do JOGA — porte fiel do protótipo v3

**Status:** concluído em grande parte; a UI atual registra cerca de 133 telas em `mobile/src/screens/` e integra endpoints reais. Telas sem endpoint permanecem visuais. A ADR 0049 rege a exibição de crédito/tickets; a UI será ajustada na 14E.
**Referência:** `telas/jogo/prototipo-v3.html` (não rastreado no Git; ver pendência de higiene).
**Regra:** preservar textos, blocos e ordem do guia; desvios exigem decisão de produto.

## O que já está portado

- **Entrada**: onboarding, telefone/OTP, passkey (visual), login, recuperação (visual).
- **Jogar**: home, fila casual/ranqueada, busca, lobby, perfil, esportes, disponibilidade, região.
- **Partidas**: lista, detalhe, check-in, relato de resultado, histórico, reserva.
- **Temporada**: XP, missões, streak, trilha, insígnias, passe.
- **Social**: amigos, clãs, chat, ranking, notificações, moderação.
- **Perfil**: divisão x nível, estatísticas, carteira, configurações, acessibilidade.
- **Quadras**: vitrine, detalhe, solicitação de reserva, pagamento Pix.

Ainda há telas fictícias, inalcançáveis e fluxos sem endpoint; ver `docs/PENDENCIAS.md`.

## Fidelidade

- Tokens copiados do CSS: fundo `#F1F3F0`, superfície `#FFFFFF`, superfície 2 `#E7EAE7`, tinta `#17191B`, texto 2 `#62686E`, linha `#D5D9D6`, amarelo `#FFD400`.
- Header de 16 px/900, sub 13 px; corpo com 16 px de margem e 14 px entre blocos; cards de 16 px, raio 18, borda 1,5.
- Tipografia: display 32, h1 30, h2 20, h3 15, lead 15, sub 14, small 13, tiny 14, label 11.
- Ícones: sprite SVG original em `mobile/src/joga/icons.ts`, renderizado com `react-native-svg` (sem Ionicons).
- Avatar: `avatarSVG` do HTML, com recorte circular, em `mobile/src/joga/avatar.tsx`.
- Tab bar de 76 px, 5 abas, ícone amarelo e traço superior na ativa.

## Ajuste forçado pelo aparelho

A barra de abas recebe respiro inferior para não ficar sob os botões de navegação do Android (3 botões). O restante do espaçamento segue o HTML.

## Backend

Neste lote as telas são visuais. O próximo lote (Entrada) conecta telefone, OTP, passkey e sessão ao backend real; depois, as telas de partida, temporada, carteira e clã usam os endpoints existentes.

## Próximos lotes

1. Entrada (boas-vindas, onboarding 1–3, telefone, OTP, passkey, login, recuperação, termos).
2. Fila, lobby, partida e check-in.
3. Quadras, reserva, T1/T2/T3.
4. Carteira, loja, checkout Pix, passe.
5. Temporada detalhada, missões, trilha, insígnias.
6. Rede, estatísticas, passaporte.
7. Clã, chat, troféus, ranking, notificações, ajustes.
