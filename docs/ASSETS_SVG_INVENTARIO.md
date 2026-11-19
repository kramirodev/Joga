# Inventário de SVGs e animações — app do jogador

**Versão:** 2.0<br>
**Data:** 17 de novembro de 2026<br>
**Status:** proposta de recorte para produção de arte; substitui a versão 1.0 (character creator).<br>
**Atualização:** 19 de novembro de 2026 — alinhamento com a ADR 0029, revisão 2, e com o catálogo implementado (`visual_catalog_items`).<br>
**Base:** ADR 0029 (sem fotos de pessoas), ADR 0043 (temporada, passe e customização), ADR 0045 (divisão × nível), ADR 0049 (ticket como unidade de exibição), `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` e as telas atuais de `mobile/src/screens/`.

> **Escopo.** Este documento cobre os assets visuais do **app do jogador**. Não cobre ícones do painel web, telas de loja, screenshots, material de marketing nem logotipos de terceiros.

> **Mudança desta versão.** O character creator foi substituído por **identidade por ícones**: ícone de perfil + moldura + cor de destaque + ícone de entrada + emote + badge. O catálogo fechado e a ausência de fotos de pessoas continuam valendo (ADR 0029).

---

## 0. Como ler esta lista

- **Único:** um arquivo SVG novo.
- **Variante:** o mesmo SVG com cor, número ou estado diferente. Não é arte nova.
- **Estado:** livre, XP ou passe, conforme a ADR 0043 §5.
- **Prioridade:** MVP (primeira entrega), T1 (temporada 1) ou depois.

Regra de economia: **não desenhar 30 níveis da trilha nem 4 tamanhos de pacote como SVGs únicos.** Use uma base + número/cor. Isso corta dezenas de arquivos.

---

## 1. Estado atual do repositório

- Existem **39 ícones genéricos** em `mobile/src/ui/icon-data.ts`, extraídos do protótipo.
- As telas usam **26** desses ícones. Não é preciso redesenhar os genéricos; o esforço novo está nos ícones de produto.
- O `Avatar.tsx` ainda é usado em telas de onboarding/social não migradas; o componente novo de identidade é `IdentityBadge.tsx`, com o catálogo em `identity.ts`. Ele será removido quando todas as telas usarem o ícone de perfil descrito na seção 3.
- O app usa `react-native-svg` e `Animated`. **Não há `lottie-react-native`.** Para o MVP, animar em SVG + `Animated` evita dependência nova; Lottie só com aprovação.

---

## 2. Decisão de identidade: ícones, não character creator

### 2.1 O modelo

A identidade do jogador passa a ser:

```text
ícone de perfil (circular)
+ moldura (bronze/prata/ouro/platina/diamante/temporada)
+ cor de destaque (6 tokens)
+ ícone de entrada (lobby/chat)
+ emote (reação)
+ badges (conquista, não compra)
```

Não há corpo, cabelo, roupa, expressão nem camadas. O ícone é a identidade; a moldura e a cor dão status; o emote dá expressão.

### 2.2 Por que

| Critério | Character creator | Ícones |
|---|---|---|
| Custo de arte | ~79 peças + camadas + QA | ~88 ícones + 6 molduras |
| Moderação | combinações ofensivas | catálogo fechado |
| Legal | mais superfície de abuso | sem pessoa, sem upload |
| Cadência de temporada | difícil produzir 7 itens/mês | 7 itens por temporada é viável |
| Backend | valida configuração de avatar | valida `icon_code` + `frame_code` |
| Performance | muitos SVGs compostos | 1 SVG + moldura |
| Identidade | mais única | suficiente com moldura/cor/badge |

### 2.3 Monetização

| Camada | Equivalente LoL | No JOGA | Ganho |
|---|---|---|---|
| Ícone | Summoner icon | Ícone de perfil | identidade |
| Moldura | Border | Moldura | status |
| Cor | Chroma | Cor de destaque | personalização |
| Entrada | Ward skin | Ícone de entrada | expressão |
| Emote | Emote | Reação de chat | social |
| Badge | Rank crest | Insígnia | conquista |

Por temporada, a ADR 0043 §11 pede **7 itens**. Composição sugerida: 3 ícones + 1 moldura + 1 cor + 1 emote + 1 ícone de entrada.

### 2.4 Impacto no backend e nos ADRs

- **ADR 0029:** a revisão 2 (2026-11-19) registra a troca de “avatar ilustrado gerado” por identidade de ícone de catálogo fechado.
- **ADR 0043 §5/§11:** categorias atualizadas para ícone de perfil, moldura, cor de destaque, ícone de entrada, emote e badge.
- **Backend:** catálogo em `visual_catalog_items` e escolha em `user_visual_identity`, com `icon_key`, `frame_key`, `accent_key`, `entry_key`, `emote_key` e `badge_key`; um equipado por slot; catálogo versionado.
- **Mobile:** `IdentityBadge.tsx` e `identity.ts` renderizam a identidade por ícones; o onboarding escolhe 1 ícone livre de cada modalidade.

---

## 3. Catálogo de ícones de identidade

**88 únicos + 6 cores (tokens).**

### 3.1 Modalidades — 18

**Futebol 5x5 (6):** bola, chuteira, trave, campo, apito, camisa 10.

**Vôlei 6x6 (6):** bola, rede, mão no passe, quadra, bloqueio, levantamento.

**Futevôlei 3x3 (6):** bola de futevôlei, rede de praia, pé descalço, sol/areia, bicicleta, ombro.

### 3.2 Posições e arquétipos — 10

Goleiro (luva), zagueiro (escudo), lateral (seta), meia (visão), atacante (chuteira/raio), levantador (mão erguida), líbero (escudo), ponteiro (seta), central (bloqueio), oposto (martelo).

### 3.3 Estilos de jogo — 10

Competitivo (espada), casual (sorriso), técnico (estrela), velocidade (raio), resistência (pulmão), fair play (aperto de mão), pontualidade (relógio), presença (check), streak (fogo), underdog (seta para cima).

### 3.4 App e marca — 8

Ticket, elo/divisão, monograma “J”, quadra, rede, calendário, mapa, escudo.

### 3.5 Conquistas — 12

Primeira partida, 10/50/100 partidas, primeira vitória, 10 vitórias, sequência de 5, quadra nova, passaporte, temporada, top 10%, fair play, fundador, beta.

### 3.6 Clã — 8

Escudo, mascote, bandeira, coroa, aliança, mural, capitão, rival.

### 3.7 Regionais e abstratos — 8

Praia, serra, urbano, noturno, dia, sol, lua, onda. **Sem estereótipo, sem mapa real, sem silhueta de cidade.**

### 3.8 Emotes — 8

Joinha, riso, choque, coração, fogo, “gg”, tchau, aplauso.

### 3.9 Molduras — 6

Bronze, prata, ouro, platina, diamante, temporada.

### 3.10 Cores de destaque — 6 tokens

Lime, azul, laranja, roxo, rosa, ciano. Não são SVGs; são variáveis de tema.

### 3.11 Coleções temáticas

Além dos ícones avulsos, organizar em coleções de temporada:

| Coleção | Conteúdo | Observação |
|---|---|---|
| Futebol de base | camisa 10, chuteira, apito, campo | sem clube real |
| Praia | bola de futevôlei, rede, sol, onda | sem pessoa |
| Noturno | lua, refletor, quadra iluminada | sem marca |
| Clássicos | troféu, medalha, escudo genérico | sem federação |
| App | ticket, elo, “J”, calendário | identidade JOGA |

---

## 4. Licenciamento e pessoas reais

**Regra:** o app não usa pessoa real, nome, apelido, silhueta reconhecível, clube, federação, marca, uniforme oficial ou número icônico sem contrato de licenciamento.

### 4.1 O que não pode

- Rosto, nome ou apelido de atleta (ex.: “Messi”, “CR7”, “Neymar”).
- Silhueta estilizada que ainda seja reconhecível como uma pessoa real.
- Escudo, mascote, cor ou uniforme oficial de clube/federação.
- Frase de efeito, celebração icônica ou número de camisa que identifique o atleta.
- Arte gerada por IA “no estilo” de uma pessoa real.

**Por quê:** direito de imagem, publicidade indireta, marca registrada, concorrência desleal e risco de o usuário interpretar endorsement. Mesmo sem lucro direto, o uso pode gerar notificação e remoção.

### 4.2 Alternativas seguras

**Arquétipos genéricos:**

- “Camisa 10”
- “O Maestro”
- “O Camisa 1”
- “O Rei da Areia”
- “O Muralha”

**Licenciamento futuro:**

- Clube ou atleta com contrato, território, prazo, aprovação de arte e revenue share.
- Coleção “Parceiros” só depois do contrato assinado.
- O ícone oficial do parceiro entra como item de temporada, não como base do produto.

**Coleções temáticas sem pessoa real:**

- “Futebol de base”
- “Praia”
- “Noturno”
- “Clássicos”
- “Cidades” (sem mapa real; textura/geométrico)

### 4.3 Exemplo “ícone do Messi”

**Não.** Nem o nome, nem o rosto, nem a silhueta, nem o “camisa 10 canhoto” identificável. Sem licença, o caminho é o arquétipo “Camisa 10” com arte genérica. Com licença, o caminho é uma coleção oficial aprovada pelo atleta/clube.

### 4.4 Processo de aprovação

1. Lista de nomes, apelidos, escudos e referências.
2. Revisão jurídica de imagem, marca e endorsement.
3. Contrato com escopo, território, prazo e aprovação de arte.
4. Arte final aprovada antes de entrar no catálogo.
5. Registro do contrato e da aprovação no inventário de itens.

---

## 5. Tickets e crédito

**16 únicos + 4 variantes.**

| # | Arquivo | O que é | Prioridade |
|---|---|---|---|
| 1 | `ticket.svg` | Ticket único, frente, com picote | MVP |
| 2 | `ticket-stack.svg` | Pilha de 3 tickets (lote) | MVP |
| 3 | `ticket-buy.svg` | Ticket com “+” (comprar) | MVP |
| 4 | `ticket-use.svg` | Ticket com seta para baixo (consumir) | MVP |
| 5 | `ticket-refund.svg` | Ticket com seta de retorno (devolução) | MVP |
| 6 | `ticket-expired.svg` | Ticket com ampulheta/x (expirado) | MVP |
| 7 | `ticket-free.svg` | Ticket com estrela (grátis de nível) | MVP |
| 8 | `ticket-pass.svg` | Ticket com calendário (cota do passe) | MVP |
| 9 | `pack.svg` | Pacote base (3/10/30/50 são variantes com número) | MVP |
| 10 | `pix.svg` | Símbolo Pix | MVP |
| 11 | `receipt.svg` | Recibo/NFS-e | MVP |
| 12 | `qr.svg` | QR code | MVP |
| 13 | `credit-lock.svg` | Cadeado “sem saque” | MVP |
| 14 | `statement.svg` | Extrato/histórico | T1 |
| 15 | `ticket-split.svg` | Ticket dividido em “quadra + JOGA” (confirmação) | MVP |
| 16 | `ticket-remaining.svg` | Ticket com saldo residual (centavos) | T1 |

**Variantes:** `pack-3`, `pack-10`, `pack-30`, `pack-50` (mesmo SVG, número/cor diferente).

> **Pix:** usar a marca oficial conforme o manual do Banco Central ou um ícone genérico de pagamento instantâneo. Não inventar uma variação da marca.

---

## 6. Elos: divisão × nível

**13 únicos.** A ADR 0045 exige ícones diferentes para os dois conceitos.

### Divisão (escudo/brasão — competitivo)

`division-bronze`, `division-silver`, `division-gold`, `division-platinum`, `division-diamond`, `division-provisional`.

### Nível (medalha/laurel — temporada)

`level-bronze`, `level-silver`, `level-gold`, `level-node` (1–30 é texto).

### Apoio

`division-up`, `division-down`, `rank-position`.

---

## 7. Temporada, passe, trilha e missões

**30 únicos.**

| Grupo | Itens |
|---|---|
| Hero | `season-hero`, `pass-hero`, `season-end` |
| Trilha | `track-node-locked`, `track-node-current`, `track-node-claimed` |
| Recompensas | `reward-icon`, `reward-frame`, `reward-accent`, `reward-emote`, `reward-badge` |
| Missões | `mission-play`, `mission-win`, `mission-new-venue`, `mission-streak`, `mission-friend`, `mission-presence` |
| Streak | `streak-0`, `streak-1`, `streak-3`, `streak-5` |
| Badges | `badge-season`, `badge-milestone`, `badge-founder`, `badge-fair-play`, `badge-streak`, `badge-clan` |
| Baú | `chest-locked`, `chest-available`, `chest-claimed` |
| Apoio | `xp-bolt`, `level-ring`, `pass-active`, `pass-expired` |

**Por temporada:** 7 itens (3 ícones, 1 moldura, 1 cor, 1 emote, 1 ícone de entrada). Produção recorrente, não baseline.

---

## 8. Reserva e partida

**32 únicos.**

| Grupo | Itens |
|---|---|
| Prazos | `timer-t1`, `timer-t2`, `timer-t3` |
| Confirmação | `confirm`, `decline` |
| Lugar | `venue`, `court`, `space`, `region`, `map-pin` |
| Preço | `price-court`, `price-joga`, `price-total` |
| Pagamento | `pix`, `ticket`, `qr`, `hold`, `payment-pending`, `payment-confirmed` |
| Cancelamento | `cancel`, `refund`, `dispute` |
| Presença | `pre-check-in`, `check-in`, `late`, `no-show`, `too-far`, `low-accuracy` |
| Fila | `substitute`, `queue`, `match-found` |
| Resultado | `win`, `draw`, `loss` |
| Estados | `booking-requested`, `booking-hold`, `booking-payment`, `booking-confirmed`, `booking-completed`, `booking-expired`, `booking-cancelled` |

---

## 9. Social e clã

**20 únicos.**

| Grupo | Itens |
|---|---|
| Amigos | `friend-add`, `friend-accept`, `friend-decline`, `friend-remove`, `friend-block`, `friend-report` |
| Convites | `invite-lobby`, `invite-clan` |
| Clã | `clan-create`, `clan-members`, `clan-ranking`, `clan-shield`, `clan-highlight` |
| Chat | `chat-send`, `chat-reply`, `chat-emote`, `chat-mute` |
| Perfil | `profile-share`, `profile-qr`, `presence-online` |

---

## 10. Estatísticas e rede

**16 únicos.**

`stat-division`, `stat-level`, `stat-progress`, `stat-position`, `stat-matches`, `stat-wdl`, `stat-presence`, `stat-streak`, `stat-season-sequence`, `stat-graph`, `stat-venue-history`, `stat-passport`, `stat-time-slots`, `stat-heatmap`, `stat-density`, `stat-trend`.

---

## 11. Sistema, estados e acessibilidade

**24 únicos.**

| Grupo | Itens |
|---|---|
| Estados | `loading`, `skeleton`, `empty`, `error`, `offline`, `success`, `warning`, `info` |
| Conta | `settings`, `security`, `passkey`, `device`, `privacy`, `terms`, `help`, `support`, `export-data`, `delete-account` |
| Acessibilidade | `a11y-font`, `a11y-contrast`, `a11y-motion`, `a11y-touch` |
| Comunicação | `bell`, `mail`, `phone`, `location`, `camera`, `photo` |

---

## 12. Animações

**18.**

| # | Arquivo | Uso |
|---|---|---|
| 1 | `anim-spinner` | carregamento |
| 2 | `anim-skeleton` | esqueleto de lista/cartão |
| 3 | `anim-booking-confirmed` | reserva confirmada |
| 4 | `anim-payment-confirmed` | Pix/ticket confirmado |
| 5 | `anim-check-in` | presença confirmada |
| 6 | `anim-level-up` | subiu de nível |
| 7 | `anim-badge-unlock` | insígnia desbloqueada |
| 8 | `anim-pass-activated` | passe ativado |
| 9 | `anim-ticket-purchase` | ticket caindo no saldo |
| 10 | `anim-match-found` | partida encontrada |
| 11 | `anim-queue-radar` | procurando partida |
| 12 | `anim-pull-refresh` | atualizar |
| 13 | `anim-streak` | chama do streak |
| 14 | `anim-season-end` | fim de temporada |
| 15 | `anim-celebration` | comemoração |
| 16 | `anim-error` | erro |
| 17 | `anim-empty` | estado vazio |
| 18 | `anim-transition` | transição de tela |

**Formato:** SVG + `Animated` no MVP (sem dependência nova). Lottie JSON só com decisão explícita e aprovação de dependência.

---

## 13. Ilustrações e app/store

**26 únicos.**

| Grupo | Itens |
|---|---|
| Onboarding | `illus-onboarding-ticket`, `illus-onboarding-match`, `illus-onboarding-venue`, `illus-onboarding-fair-play` |
| Empty states | `illus-empty-bookings`, `illus-empty-matches`, `illus-empty-friends`, `illus-empty-notifications`, `illus-empty-search`, `illus-empty-history` |
| Erros | `illus-error-offline`, `illus-error-generic` |
| Hero | `illus-recap`, `illus-pass`, `illus-ticket`, `illus-venue-placeholder`, `illus-profile-placeholder` |
| Clã | `illus-clan-shield-placeholder` |
| App/store | `app-icon`, `app-icon-foreground`, `app-icon-background`, `app-icon-monochrome`, `splash`, `notification-icon`, `favicon`, `store-feature-graphic` |

---

## 14. Resumo e prioridade

| Grupo | Únicos | Variantes |
|---|---:|---:|
| Ícones de identidade | 88 | cor |
| Tickets/crédito | 16 | 4 |
| Elos | 13 | 0 |
| Temporada/passe | 30 | por temporada |
| Reserva/partida | 32 | estados |
| Social/clã | 20 | 0 |
| Estatísticas/rede | 16 | 0 |
| Sistema/acessibilidade | 24 | 0 |
| Animações | 18 | 0 |
| Ilustrações/store | 26 | 0 |
| **Total** | **~283** | **~60** |

**Ordem sugerida:**

1. **MVP (~100):** 18 ícones de modalidade, 6 molduras, 8 emotes, 12 conquistas, tickets, elos, 10 sistema, 6 animações, 8 ilustrações.
2. **Temporada 1 (~50):** 7 itens da temporada, posições, estilos, app/marca, clã, regionais.
3. **Depois (~50):** rede/inteligência, acessibilidade, coleções temáticas e parceiros licenciados.

---

## 15. Regras de produção

### Formato

- **Ícone de identidade:** 512×512 de export, exibição 96×96 e 48×48, área segura circular, 2–3 cores + acento.
- **Moldura:** 512×512, overlay transparente, sem cobrir o centro do ícone.
- **Ícone de UI:** 24×24, `stroke` 1,75, `currentColor`, sem `fill`.
- **Emote:** 128×128, fundo transparente, leitura em 32×32.
- **Ilustrações:** 320×240 ou 1:1, flat, 2–3 cores + acento; variante dark quando necessário.
- **Animações:** SVG + `Animated` no MVP; Lottie só com aprovação.

### Nomes

```text
icon-<categoria>-<nome>.svg
frame-<tier>.svg
emote-<nome>.svg
ticket-<estado>.svg
elo-<tipo>-<tier>.svg
anim-<evento>.svg
illus-<contexto>.svg
```

### Pastas sugeridas

```text
mobile/src/ui/assets/icons/
mobile/src/ui/assets/identity/
mobile/src/ui/assets/frames/
mobile/src/ui/assets/emotes/
mobile/src/ui/assets/tickets/
mobile/src/ui/assets/elos/
mobile/src/ui/assets/season/
mobile/src/ui/assets/booking/
mobile/src/ui/assets/social/
mobile/src/ui/assets/stats/
mobile/src/ui/assets/system/
mobile/src/ui/assets/anim/
mobile/src/ui/assets/illus/
```

### Acessibilidade

- Ícones com `accessibilityLabel` e contraste mínimo.
- Nunca depender só de cor para estado (usar forma + rótulo).
- Respeitar “reduzir movimento”: animações têm variante estática.
- Alvos de toque de 44×44 no mínimo; o SVG pode ser 24×24 dentro do alvo.

### Licenciamento

- Sem pessoa real, clube, federação ou marca sem contrato.
- Pix: marca oficial conforme manual do Banco Central, ou ícone genérico.
- SVGs próprios, sem fonte externa não licenciada.
- Coleções de parceiros só com contrato e arte aprovada.

---

## 16. Checklist de entrega

- [ ] 88 ícones de identidade (modalidades, posições, estilos, app, conquistas, clã, regionais, emotes, molduras).
- [ ] 6 cores de destaque como tokens.
- [ ] 16 SVGs de tickets/crédito + 4 variantes de pacote.
- [ ] 13 SVGs de elos (divisão × nível).
- [ ] 30 SVGs de temporada/passe/trilha/missões.
- [ ] 32 SVGs de reserva/partida.
- [ ] 20 SVGs de social/clã.
- [ ] 16 SVGs de estatísticas/rede.
- [ ] 24 SVGs de sistema/estado/acessibilidade.
- [ ] 18 animações.
- [ ] 26 ilustrações + app/store.
- [ ] Exportação otimizada (SVGO), `viewBox` correto, sem texto solto.
- [ ] Variantes dark/light verificadas.
- [ ] Nomes e pastas conforme a seção 15.
- [ ] Lista de licenças e aprovações de arte.

---

## 17. Pendências e decisões

1. **ADR 0029:** atendido pela revisão 2, que troca “avatar ilustrado” por “identidade por ícone de catálogo fechado”.
2. **ADR 0043 §5/§11:** atendido; categorias de item passam a ícone de perfil, moldura, cor de destaque, ícone de entrada, emote e badge.
3. **Backend:** implementado com `visual_catalog_items` e `user_visual_identity` (`icon_key`, `frame_key`, `accent_key`, `entry_key`, `emote_key`, `badge_key`); um equipado por slot.
4. **Mobile:** `IdentityBadge.tsx`/`identity.ts`; onboarding escolhe 1 ícone livre por modalidade.
5. **Catálogo:** o número de 88 é baseline; o catálogo final depende de produto.
6. **Lottie:** decidir se o app aceita a dependência ou se as animações ficam em SVG + `Animated`.
7. **Pix:** confirmar uso da marca oficial e revisão de licenciamento.
8. **Parceiros:** nenhuma coleção de atleta/clube antes de contrato, território, prazo e aprovação de arte.
