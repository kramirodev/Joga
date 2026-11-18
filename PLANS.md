# Roadmap de desenvolvimento — JOGA

Este roadmap define dependências e critérios de saída. Cada fase deve ganhar um arquivo próprio em `harness/build/` antes da implementação. Não executar várias fases com um único pedido ao Codex.

## Visão geral

| Fase | Nome | Objetivo de saída | Dependência |
|---|---|---|---|
| 0 | Repositório e governança | Repositório `kramirodev/Joga`, documentação e fluxo de trabalho definidos | Nenhuma |
| 1 | Prova técnica mobile/nativa | Build Android/iOS e provas de passkey, localização e integrações críticas | 0 |
| 2 | Fundação de engenharia | Esqueletos mobile/backend, ambiente local, CI e health checks | 1 |
| 3 | Identidade e segurança | Cadastro por telefone, OTP, passkeys, sessões e recuperação segura | 2 |
| 4 | Perfil e descoberta | Perfil esportivo, modalidades, disponibilidade, locais e busca manual/GPS | 3 |
| 5 | Filas e matchmaking | Filas persistentes, worker e formação idempotente de partidas | 4 |
| 6 | Ciclo de partidas | Confirmação, presença, expiração e máquina de estados | 5 |
| 7 | Resultados e disputas | Relatos, divergência, evidências e resolução auditável | 6 |
| 8 | Competitivo | MMR versionado, ranking e Trust Factor separados | 7 |
| 9 | Comunicação em tempo real | WebSocket autorizado, Outbox, push, amigos/convites e reconciliação | 6; integra 8 quando aplicável |
| 10 | Hardening e piloto | Segurança, carga, observabilidade, backup/restore e lançamento controlado | 3–9 |
| 11 | Organizações e painel de gestão | Organizações, membros, papéis, isolamento e painel web dos estabelecimentos (JOGA y GESTÃO) | 3 |
| 12 | Quadras, agenda e fornecedor | Espaços, agenda, preço do espaço, bloqueios e cadastro CNPJ/Pix do fornecedor | 11 |
| 13 | Reservas e temporizadores | Solicitação, aceite, bloqueio, T1/T2/T3, substituição e máquina de estados | 12 |
| 14 | Pagamentos, crédito e reembolsos | PSP, compra de crédito, webhooks, ledger, estorno e conciliação | 13 |
| 14D | Crédito, carteira e temporada | Pacotes e passe, exibição em tickets, carteira, XP, trilha e catálogo cosmético | 12, 14 |
| 14E | Realinhamento ADR 0049 | Ledger em reais, preço em duas linhas, taxa, CPF, NFS-e placeholder e migração do crédito | 14, 14D |
| 14B | Hardening do Mercado Pago | Credenciais reais, reembolso, MED/chargeback, conciliação externa e métricas | 14E; pareceres |
| 15 | Interface financeira do fornecedor | Extrato, repasses a receber, contestação e conciliação do fornecedor | 14B, 14E |
| 16 | Clãs e troféus | Clãs abertos/fechados, chat de clã, troféus por modalidade e temporadas | 8 |
| 17 | Moderação e Trust & Safety | Denúncias de perfil, análise contextual, medidas e revisão humana | 9, 16 |
| 18 | Publicidade | Quadras, estabelecimentos e marcas patrocinados, sem efeito competitivo | 13, 15, 19A |
| 19A | Jurídico, fiscal e LGPD | Pareceres, contratos, CPF/NFS-e, custódia e retenção | 14E, 15 |
| 19B | Hardening final e lançamento comercial | Hardening completo, LGPD, revisão jurídica e go-live comercial | 10, 14B, 15, 18, 19A |

> **Escopo do MVP.** Clãs e troféus (**Fase 16**) passam a integrar o MVP e são pré-requisito do primeiro evento de marketing, conforme a **ADR 0044**. A fase pode rodar em paralelo com as Fases 11 a 15, mantendo a dependência técnica da Fase 8, e precisa estar concluída antes da Fase 19B.

> **Precedência da ADR 0049.** A ADR 0049 é a decisão vigente sobre unidade de conta, preço e custódia. Ela substitui, no que conflitar, a ADR 0042 §1.2, §2.1, §2.2, §2.6, §3 (tabela 2D como preço) e §5.7, e a ADR 0048 §5. O saldo é expresso em reais; o ticket, quando existir, é **unidade de exibição 1:1**, sem efeito jurídico, contábil ou fiscal autônomo. O saldo em reais não é exibido como carteira; o valor do espaço, a taxa e a tabela de conversão tickets ↔ faixa/valor são exibidos antes da confirmação, e a NFS-e materializa o valor. Evitar terminologia de natureza monetária para ticket. A **Fase 14E** concentra essa transição; até a aprovação dos pareceres, dinheiro real permanece bloqueado.

## Fase 0 — Repositório e governança

**Escopo:** desenvolver o JOGA como projeto independente, do zero, no repositório `kramirodev/Joga`; preparar documentação, governança, README e templates de PR; definir `main` estável e branches curtas. O repositório anterior pode ser consultado apenas como referência conceitual, sem dependência operacional.

**Não fazer:** implementar endpoints, telas, tabelas de negócio, autenticação ou matchmaking.

**Aceite:** arquivos `AGENTS.md`, `GOALS.md`, `PLANS.md`, `PROMPTS.md` e documentação técnica estão no lugar; `README.md` apresenta o projeto e orienta a documentação; decisões e pendências têm fase responsável; `harness/build/phase-00-repositorio-e-governanca.md` registra escopo e evidências; `git diff --check` passa; o repositório `kramirodev/Joga` está provisionado e vinculado; nenhuma credencial é adicionada. Nenhuma atividade relativa ao repositório anterior é exigida.

## Fase 1 — Prova técnica mobile/nativa

**Escopo:** comparar Expo development build e React Native CLI; criar protótipo mínimo para abrir em Android e iOS; provar o caminho de registro/autenticação com passkey; validar arquivos de associação de domínio; testar permissões de localização aproximada, precisa e negada; validar integração de SMS em sandbox ou adapter simulado.

**Não fazer:** construir telas completas, fluxo de conta em produção, matchmaking ou banco de dados de negócio.

**Aceite:** decisão técnica documentada em ADR, com versões, limitações e evidências de execução nos dois sistemas. Se um caminho não puder ser testado em uma plataforma, registrar bloqueio; não declarar suporte multiplataforma completo.

## Fase 2 — Fundação de engenharia

**Escopo:** criar estrutura `mobile/`, `backend/`, `infra/`, testes e CI; configurar versões fixadas, lint, formatadores, type checks, testes mínimos, PostgreSQL/PostGIS local e gestão de configurações. Redis pode ficar desligado até existir uso real.

**Não fazer:** funcionalidades de produto ou arquitetura distribuída.

**Aceite:** app abre em dispositivo/emulador; API sobe; endpoint de health verifica dependências corretamente; migração inicial vazia aplica em banco descartável; CI valida os dois projetos; instruções locais reproduzíveis.

## Fase 3 — Identidade e segurança

**Escopo:** telefone E.164, desafios OTP limitados e de uso único, passkey, sessão/refresh rotativo, dispositivos, logout, revogação e recuperação; adaptador de SMS simulado no desenvolvimento.

**Não fazer:** confiar em SMS como único fator de recuperação; armazenar OTP ou refresh token em texto puro; integrar provedor real sem autorização.

**Aceite:** testes de replay, expiração, força bruta, rotação, revogação, reutilização de refresh token, troca de telefone e acesso entre contas; passkey testada em Android e iOS.

## Fase 4 — Perfil e descoberta

**Escopo:** perfil, modalidades, formatos, nível inicial autodeclarado, disponibilidade, locais e descoberta geoespacial. Localização só em primeiro plano; alternativa manual obrigatória.

**Não fazer:** rastreamento contínuo, exposição da coordenada residencial ou ranking competitivo.

**Aceite:** GPS negado/aproximado não bloqueia busca manual; validação de coordenadas/raio no servidor; consultas PostGIS limitadas e paginadas; autorização e minimização verificadas.

## Fase 5 — Filas e matchmaking

**Escopo:** entrada/saída de fila persistida no PostgreSQL, compatibilidade, worker e formação transacional de partidas; idempotência; locks e constraints.

**Não fazer:** usar Redis como fonte oficial, gerar partidas somente em memória ou implementar algoritmo opaco sem testes.

**Aceite:** testes concorrentes demonstram ausência de duplicidade; falha/restart de worker é recuperável; entradas inconsistentes são reconciliadas; algoritmo e versão ficam registrados.

## Fase 6 — Ciclo de partidas

**Escopo:** máquina de estados central, confirmação/recusa, prazo, expiração, presença e cancelamento.

**Não fazer:** transições livres por endpoint ou penalidade automática baseada somente em GPS.

**Aceite:** matriz de transições válidas/inválidas testada; requisições repetidas não duplicam ações; usuários só atuam em partidas das quais participam.

## Fase 7 — Resultados e disputas

**Status:** implementada no backend e integrada à `main`; a UI mobile cobre o relato principal, mas confirmação de resultado, segunda rodada e disputa ainda não têm fluxo completo. Pendências: revisar a retenção provisória do ADR 0024 e configurar `JOGA_REVIEW_OPERATORS`.

**Escopo:** relatos autorizados com três resultados possíveis (equipe A, equipe B ou empate esportivo quando o formato permitir), janela de 10 minutos controlada pelo backend, quórum `ceil(elegíveis/2)`, resultado por maioria simples, evidência textual privada de até 2.000 caracteres, divergências, segunda rodada de 5 minutos em empate na primeira posição ou divergência exata de 50%, análise interna, revisão humana por CLI/script auditável e decisão registrada. Inclui o desempate de resultado exatamente em 50%: segunda confirmação com histórico preservado e, persistindo o empate, análise interna avaliada relato a relato (sem média de grupo, com capitães como sinal sem peso automático), revisão humana quando inseguro, anulação como último recurso e MMR congelado durante todo o processo (conceito §9.4; ADRs 0008 e 0023).

**Decisões já aprovadas:** não existe tolerância separada de “1–2 votos”; a regra é o limite de 50% sobre votos válidos — abaixo de 50% finaliza, exatamente 50% abre segunda rodada, acima de 50% abre disputa. Votos ausentes ou anulados não entram no denominador. A segunda rodada apresenta todas as alternativas permitidas pelo formato e não há terceira rodada. O capitão da Fase 7 é provisório: maior número de partidas válidas concluídas (`FINALIZED`) do mesmo formato, anteriores à partida atual, e, em empate, UUID; sem critério de nível; seleção na formação e não retroativa. Evidência é apenas textual, privada, com limite de 2.000 caracteres e uma por participante por disputa. A fase é backend-only e não implementa nem atualiza MMR. A CLI exige operador autorizado e motivo.

**Não fazer:** aplicar MMR antes de resultado final; majority vote como antifraude universal; sobrescrever relatos antigos; tornar visível aos participantes a análise interna de confiabilidade; criar telas mobile; implementar upload de arquivos; criar painel administrativo completo; alterar capitães ou resultados históricos.

**Aceite:** resultados conflitantes entram em disputa; partida disputada não altera rating; evidências têm limites de formato/tamanho/acesso; decisão é auditável; três resultados são tratados corretamente; quórum e votos ausentes/anulados são respeitados; segunda rodada tem prazo próprio e alternativas definidas; capitão provisório é determinístico e registrado; contrato HTTP e códigos de erro implementados conforme o plano.

**Pontos abertos após a implementação:** revisar a retenção provisória do ADR 0024 na fase de LGPD; configurar a lista de operadores autorizados da CLI (`JOGA_REVIEW_OPERATORS`). Ver ADR 0023, ADR 0024 e `harness/build/phase-07-resultados-e-disputas.md`.

## Fase 8 — Sistema competitivo

**Status:** implementada no backend e no mobile; a leitura competitiva usa divisão/progresso e nunca expõe MMR bruto. Integrada à `main`; painel administrativo não faz parte da fase.

**Escopo:** rating inicial simples/versionado, histórico append-only, ranking e Trust Factor separado.

**Não fazer:** rating editável pelo cliente ou painel; apagar histórico; denúncia isolada gerar punição definitiva.

**Aceite:** aplicação única por partida/versão; correções compensatórias; simulações do algoritmo; casual não altera rating ranqueado; contestação e auditoria para sinais de confiança.

## Fase 9 — Comunicação em tempo real

**Status:** 9A, 9B, 9C implementados em 2026-11-06 (backend + mobile + retenção provisória); 9D (central de notificações persistida, leitura e gatilhos de reserva/partida) implementado no backend em 2026-11-14. Push real e dispatcher de notificações pendentes.

**Escopo:** WebSocket autenticado e autorizado, Outbox transacional, push por adaptadores, gestão de tokens de dispositivo, reconciliação de notificações, lista de amigos com convites a lobbies, bloqueios e limites contra spam.

**Não fazer:** conexões em memória como mecanismo de coordenação entre processos; confiar em evento entregue como prova de estado; chat global universal; envio livre de mídia.

**Aceite:** reconnect recupera estado via API; evento duplicado não duplica efeito; sessões expiradas/revogadas perdem acesso; falha push/WebSocket não corrompe a partida; convite de lobby respeita bloqueio, privacidade e limites.

## Fase 10 — Hardening e piloto (núcleo esportivo)

**Status:** 10A (hardening backend local) concluído em 2026-11-06; piloto real pendente.

**Escopo:** threat modeling atualizado, testes de segurança, carga, observabilidade, alertas, backups e restauração, política de retenção, revisão LGPD, rollout controlado do núcleo esportivo. O hardening final, a revisão LGPD completa e o lançamento dos módulos comerciais ocorrem na Fase 19.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo de SMS/maps/infra definidos; piloto monitorado.

## Fase 11 — Organizações e painel de gestão

**Status:** 11A (fundação backend), 11B (painel web) e 11C (CSP, testes de UI e observabilidade) implementados, validados localmente e integrados à `main`; sem deploy.

**Escopo:** organizações/estabelecimentos esportivos, membros, papéis e permissões por recurso; painel web responsivo autenticado (JOGA y GESTÃO) com cadastro e consulta das operações originadas no JOGA; auditoria de ações administrativas. Framework web registrado em ADR próprio.

**Não fazer:** expor o painel a consumidores; permitir acesso a dados de outra organização; substituir ERP; iniciar reservas pagas, pagamentos, clãs ou publicidade; criar catálogo ou estoque de produtos.

**Aceite:** membro de um estabelecimento não consegue ler nem alterar recursos de outro (testes BOLA/cruzados); papéis respeitados por ação; contratos HTTP versionados com schemas explícitos; identidade compartilhada com o app sem criar conta separada por papel.

## Fase 12 - Quadras, agenda e fornecedor

**Status:** 12A (quadras, fotos, agenda e preço do espaço) implementada e validada localmente; 12B (cadastro do estabelecimento como fornecedor e chave de repasse) implementada tecnicamente, mas sem KYC contratual. O modelo de preço será revisto pela Fase 14E (ADR 0049).

**Escopo 12A — quadras, fotos e agenda:** cadastro de espaços/quadras, **preço do espaço definido pelo estabelecimento e tabela de conversão tickets ↔ faixa/valor como exibição, nunca como preço jurídico (ADR 0049 §2.3/§2.4)**; vínculo esporte–quadra, fotos de quadra com upload autenticado por organização, revisão, armazenamento privado, remoção e retenção; agenda, intervalos, bloqueios, exceções e registro de reservas externas para evitar conflito; ligação entre o catálogo `venues` da Fase 4 e o perfil comercial `organization_venues` da Fase 11.

**Escopo 12B — fornecedor e repasse:** dados cadastrais do estabelecimento, CNPJ, chave Pix ou conta bancária de titularidade do próprio CNPJ, contrato de intermediação e regra que impede reserva paga sem chave de repasse validada. Não há KYC de recebedor de marketplace: a quadra é fornecedora e recebe por repasse; escrow/conta vinculada é decisão da fase comercial (ADR 0049 §2.8).

**Não fazer:** exigir integração ERP/PDV; implementar logística, produtos ou estoque; permitir reserva paga para fornecedor sem chave de repasse; tratar a tabela de conversão como preço jurídico; representar espaço público como reservável sem autorização verificável; aceitar foto de pessoa, upload livre ou URL arbitrária; publicar foto sem revisão.

**Aceite:** dois usuários não reservam o mesmo intervalo; constraints e transações protegem sobreposição; agenda respeita fuso e duração do formato; fornecedor sem chave de repasse válida não abre cobrança; estados do fornecedor são consultáveis e auditáveis; estabelecimento só acessa a própria agenda; foto só é exibida após revisão e vínculo com organização ativa; membro de outra organização não lê, envia, revisa nem remove foto; remoção e retenção são auditáveis.

## Fase 13 — Reservas e temporizadores

**Status:** 13A (backend de reservas, holds e T1/T2/T3), 13B (painel mobile de reservas e ajustes de painel), 13C (vitrine reservável, criação ponta a ponta, portão de payout e snapshot de faixa), 13D (payout, cobertura, reajuste, cancelamento, reembolso e presença no painel) e 13E (T2 em horário comercial, reserva automática do lobby e dispatcher de notificações) implementados e validados localmente. Parte da 13C–13E está na branch de trabalho, ainda sem merge; push real e pagamentos reais continuam pendentes.

**Escopo:** solicitação de reserva ao estabelecimento, aceite/recusa, bloqueio temporário do espaço específico, T1 (confirmação de participação), T2 (resposta do estabelecimento), T3 (confirmação de participação e acesso), expiração, substituição de participantes, cancelamento antes da confirmação, origem `JOGA` e máquina de estados auditável. **No fluxo de crédito não há cobrança na reserva:** o crédito é consumido na confirmação (ADR 0042, com a unidade contábil da ADR 0049). O fluxo de reserva avulsa mantém a cobrança por participante.

**Não fazer:** abrir cobrança antes do aceite e do bloqueio; confirmar reserva sem todos os pagamentos no fluxo avulso ou sem saldo suficiente no fluxo de crédito; permitir transição livre por endpoint; prorrogar bloqueio ou reiniciar prazo na substituição; cobrar comissão de reserva externa sem acordo explícito; tratar ticket como unidade contábil.

**Aceite:** dois usuários não bloqueiam o mesmo intervalo; timers controlados pelo backend e idempotentes; substituição não duplica vaga nem cobrança; no fluxo avulso a reserva não confirma com pagamento incompleto e no fluxo de crédito não confirma sem saldo suficiente; usuário só atua em reservas das quais participa; matriz de transições válidas/inválidas testada.

## Fase 14 - Pagamentos, crédito e reembolsos

**Status:** 14A (Mercado Pago Orders API, Pix, webhook e ledger) e 14C (reembolsos, extrato e conciliação com PSP simulado) implementadas e validadas localmente em 2026-11-07. O Mercado Pago é o PSP do protótipo com jogadores reais (ADR 0048); Inter/Pagar.me ficam para o futuro e não bloqueiam a fase. A 14E é pré-requisito para dinheiro real no novo modelo. Pendentes: validação com credenciais reais, reembolso real, MED/chargeback e conciliação externa (Fase 14B).

**Escopo:** integração com PSP, compra de crédito e de passe; **Mercado Pago (Orders API) no protótipo com jogadores reais** (ADR 0048); webhooks autenticados e idempotentes; ledger financeiro auditável em reais (ADR 0049); estorno parcial de Pix nos 7 dias do CDC; repasse ao fornecedor em `starts_at + 2h` (ADR 0040); conciliação básica. O fluxo de crédito segue a ADR 0042 e a 0049 e não usa split nem recebedor de marketplace.

**Não fazer:** construir processador próprio ou carteira custodial; armazenar dados completos de cartão; confiar no retorno visual do app; abrir cobrança antes do bloqueio; liberar valor ao fornecedor antes da confirmação; deduzir tarifas do reembolso do jogador; reconhecer crédito não usado como receita.

**Aceite:** status financeiro só muda por evento autenticado ou consulta server-to-server; replay de webhook não duplica pagamento, vaga ou reembolso; reembolso devolve principal e taxa; cobrança de participante substituído vai para reembolso; ledger de dupla entrada e PSP permanecem conciliáveis; autorização negativa entre reservas testada.

## Fase 14D - Crédito, carteira e temporada

**Status:** fatias **14D.1 a 14D.16** implementadas entre 2026-11-12 e 2026-11-14 como **protótipo do modelo de crédito**. A camada de conta, preço e custódia será realinhada pela **Fase 14E** (ADR 0049) antes de qualquer uso com dinheiro real. A UI mobile cobre carteira, passe, temporada, missões, badges e estatísticas; faltam inventário/loadout, retrospectiva, reembolso de pacote/passe e calibração de produto.

**Depende de:** 12 (espaços e fornecedor) e 14 (PSP e ledger). Alimenta as Fases 14E, 15, 19A e 19B.

**Escopo:** crédito comprado em reais, exibido em tickets 1:1; pacotes e passe trimestral com franquia mensal; tabela de conversão tickets ↔ faixa/valor exibida antes da confirmação, sem ser preço jurídico; consumo na confirmação e devolução em crédito conforme a ADR 0039/0049; carteira; XP em ledger append-only; trilha de 30 níveis, missões semanais, streak de vitórias e nível de temporada; catálogo cosmético em três estados, com atribuição e revogação de itens de passe; ingressos grátis por nível; estatísticas pessoais (divisão/progresso, evolução, histórico por quadra, passaporte, horários e retrospectiva); inteligência de rede; crédito de estreia.

**Não fazer:** tratar ticket como unidade de conta ou saldo jurídico; exibir saldo em reais como carteira; expirar crédito comprado; transferir, revender ou sacar crédito; lançar rendimento de float ou breakage como receita; mapa de calor de evento de jogo; qualquer item que altere MMR, Trust Factor, matchmaking ou troféu de clã; expor MMR bruto; transformar a inteligência de rede em filtro de matchmaking; exibir célula de rede abaixo da amostra mínima.

**Aceite:** compra idempotente por chave; consumo idempotente por reserva; devolução em crédito conforme a matriz da ADR 0039; tabela de conversão exibida e versionada, sem ser preço; XP sem duplicidade por `ref_id`; nível e atribuição reconstruíveis a partir do ledger; item de passe revogado ao fim do ciclo; nenhum item altera competitividade; ledger em reais conciliável com o PSP; passe com período mensal não acumulável; estatísticas essenciais e do passe conforme a ADR 0045; MMR bruto nunca exposto; nenhuma célula de rede abaixo da amostra mínima.

## Fase 14E — Realinhamento da ADR 0049

**Status:** **implementada, pendente de revisão/commit**. Etapas 0–11 e 6b concluídas em 2026-11-17: plano de contas, preço em duas linhas, ledger de dupla entrada, tabela 2D como unidade de consumo, passe/grátis/admin, CPF/NFS-e placeholder/termos, aposentadoria dos ledgers legados, extrato/comissão e janela de contestação. Suíte de referência: **595 passed, 30 skipped** antes das correções finais; head `v6a7b8c9d0e1`. **Bloqueada para dinheiro real** até 14B e pareceres; pareceres jurídico/fiscal permanecem ignorados no protótipo por decisão de 17/11/2026. 14B e 18 não iniciadas.

**Depende de:** 14 e 14D congeladas. Alimenta 14B, 15, 19A e 19B.

**Escopo:** saldo e ledger em reais (centavos) como fonte da verdade; ticket como unidade de exibição 1:1, sem efeito jurídico, contábil ou fiscal autônomo; preço em duas linhas — valor do espaço e taxa de intermediação; persistência de `venue_price_cents`, `fee_cents`, `fee_percent_applied` e `total_cents` na reserva; percentual uniforme e piso configuráveis; integração do ledger de dupla entrada aos fluxos de reserva, compra, passe, reembolso e repasse; crédito comprado sem expiração; passe como franquia mensal não acumulável e fora do escrow; CPF cifrado; NFS-e como intenção/documento fiscal por reserva; termos e aceite; migração dos lotes existentes pelo preço unitário efetivamente pago; remoção dos caminhos de conta antigos.

**Não fazer:** tratar ticket como unidade de conta ou saldo jurídico; exibir saldo em reais como carteira; expirar crédito comprado; reconhecer crédito não usado como receita; usar a tabela 2D como preço jurídico; abrir dinheiro real antes dos pareceres; fixar alíquota ou custódia em código; criar abstração de escrow sem fornecedor definido.

**Aceite:** toda obrigação financeira nasce no ledger em reais; a reserva guarda preço do espaço, taxa, percentual e total congelados; o ticket exibido é 1:1 com o crédito e o saldo em reais não é exibido; o valor do espaço, a taxa e a tabela de conversão aparecem antes da confirmação; a NFS-e é registrada por reserva; crédito comprado não expira; franquia de passe tem período mensal e não se acumula; migração de saldos é idempotente e auditável; nenhum fluxo usa `booking_ledger_entries`, `ticket_ledger` ou `payment_events` como ledger principal; testes de conciliação, replay e autorização passam.

## Fase 14B — Hardening do Mercado Pago

**Status:** não iniciada. Formaliza o que hoje é citado como “14B” em `docs/PENDENCIAS.md`; depende da 14E e dos pareceres.

**Depende de:** 14E; contrato e credenciais reais; revisão jurídica/fiscal.

**Escopo:** validação com credenciais reais; reembolso real; MED/chargeback; conciliação externa com o PSP; retry e replay de webhook; métricas e alertas de pagamento; runbook operacional; tratamento de divergência sem alterar saldo do jogador.

**Não fazer:** liberar dinheiro real sem parecer; tratar chargeback como receita negativa do jogador; usar o retorno do app como confirmação; ocultar taxa ou ajuste.

**Aceite:** pagamento, reembolso e repasse conciliam com o extrato do PSP; replay não duplica; MED/chargeback bloqueia repasse e gera receivable contra o fornecedor; alertas e runbook existem; nenhuma operação exige intervenção manual não auditada.

## Fase 15 — Interface financeira e conciliação

**Status:** **15A entregue** no backend, refeita sobre o ledger de dupla entrada em reais: extrato por reserva/repasse, recebíveis com janela de contestação de **72 h persistida**, comissão do JOGA separada, contestação com decisão auditável, comprovante simulado, NFS-e placeholder e hook de MED. **15B pendente de painel**: a aba Financeiro ainda precisa consumir os campos novos. A ADR 0039 define cancelamento, substituição, presença e ausência; a ADR 0040 define repasse em `starts_at + 2h`; a ADR 0041 define o Trust Factor. Política de 17/11/2026: antes do cutoff há devolução integral e sem repasse; depois do cutoff/no-show não há devolução e a quadra recebe integral com repasse; quadra que cancela devolve tudo e não recebe; contestação aberta congela o repasse. Não existe reembolso parcial. Repasse real, MED/chargeback real, comprovante real, NFS-e operacional e conciliação externa continuam em 14B/19A.

**Escopo:** interface financeira do fornecedor com extrato por reserva e por repasse, agenda de repasses a receber, status, comprovantes, dados contratuais, canal de contestação, histórico de estornos e relatório de comissão; **repasse em `starts_at + 2h`** (ADR 0040); conciliação periódica em reais; tratamento de MED, chargeback e estorno sem saldo; obrigações de transparência aplicáveis. O fornecedor recebe o valor do espaço; a comissão é receita do JOGA. Não há split nem recebedor de marketplace.

**Não fazer:** repassar antes da confirmação; esconder taxas ou ajustes; transformar a interface em ERP; executar ajuste manual irreversível sem justificativa e auditoria; tratar repasse como garantia automática contra MED; chamar o valor do fornecedor de receita do JOGA.

**Aceite:** repasse idempotente e registrado no ledger em reais; extrato do fornecedor bate com o PSP; contestação tem prazo, canal e decisão auditável; fornecedor só vê os próprios dados; relatório de repasses reproduzível; eventos de MED e estorno sem saldo registrados e tratados; NFS-e de cada reserva referenciada.

## Fase 16 — Clãs e troféus

**Status:** antecipada para o **escopo do MVP** pela ADR 0044 e **implementada no backend em 2026-11-13** (ADR 0046), na branch de trabalho. Clãs de até 30 membros com entrada por aprovação, papéis, carência de 7 dias, chat com denúncia e ocultação imediata, troféus por temporada/formato com os 10 melhores membros e snapshot no fechamento. A UI mobile existe parcialmente; faltam administração de clã, testes de UI e a moderação completa da Fase 17.

**Escopo:** clãs abertos/fechados com membros, administradores, convites e limites; chat de clã em texto e referências internas; vínculo clã–jogador na data de cada partida; troféus por modalidade com fórmula-base 50/30/20 versionada, considerando os 10 melhores membros elegíveis, temporadas configuráveis e snapshots; ciclo de moderação do chat segue a Fase 17.

**Não fazer:** aceitar pontos enviados pelo cliente; permitir compra, pagamento ou publicidade de pontos; somar modalidades em um ranking único; implementar ranking público sem simulação e testes de abuso.

**Aceite:** mudança de clã não transfere troféus retroativos; participação tem limites contra volume artificial; elegibilidade exige permanência mínima; temporada encerra com snapshot auditável; chat de clã acessível só a membros autorizados.

## Fase 17 - Moderação e Trust & Safety

**Status:** 17A (denúncia de perfil no lobby, contexto limitado, triagem determinística, revisão humana por CLI, medidas reversíveis, recurso e auditoria), 17B (cooldown para denúncia falsa, suspensão temporária com reativação, retenção/redação e limites operacionais) e 17C (identidade de operador, fila interna, notificação persistida, painel web separado em `/moderation` e central interna) implementadas no backend e no painel em 2026-11-14/15, na branch de trabalho. Sem IA paga e sem suspensão permanente. O classificador local/open-source continua pendente.

**Escopo:** denúncia de perfil no lobby com categorias definidas e seleção de até cinco mensagens + janela limitada de contexto; moderação assistida por IA (classificação, agrupamento, priorização, medidas preventivas proporcionais e reversíveis, níveis de confiança); revisão humana em ferramenta interna separada do painel de gestão; recursos contra penalizações; histórico auditável de decisões; retenção e acesso limitados.

**Não fazer:** moderação de mídia enviada por usuários (o MVP não tem upload livre em perfil, lobby ou chat); moderação de fotos de quadra, que tem fluxo próprio na Fase 12; suspensão permanente definida apenas por IA; denúncia isolada reduzir Trust Factor; encaminhar toda conversa continuamente para análise.

**Aceite:** só participantes do lobby denunciam e só mensagens da própria conversa podem ser anexadas; medidas proporcionais com justificativa, reversibilidade das automáticas e possibilidade de contestação; acesso a conteúdo de moderação restrito a funções autorizadas e registrado.

## Fase 18 — Publicidade

**Status:** não iniciada. Bloqueada pela 15 e pela 19A; não abrir antes de haver audiência e base financeira reconciliada.

**Escopo:** estabelecimentos e quadras em destaque, campanhas de marcas, identificação visual de anúncios, registros de impressão/clique/conversão com minimização de dados e LGPD.

**Não fazer:** alterar MMR, Trust Factor, matchmaking, composição de equipes ou rankings por pagamento; violar filtros do usuário; tratar publicidade como receita antes de audiência; criar catálogo ou venda de produtos.

**Aceite:** posições patrocinadas identificadas; filtros obrigatórios respeitados; métricas auditáveis e sem dados desnecessários; completude comercial documentada antes do go-live.

## Fase 19A — Jurídico, fiscal e LGPD

**Status:** não iniciada e bloqueante para 18 e 19B.

**Escopo:** pareceres fiscal e jurídico da ADR 0049; contrato de intermediação e termos; CPF e NFS-e; custódia B→C; retenção de mensagens, evidências e dados financeiros; exclusão de conta e devolução de saldo; política de cancelamento/reembolso; revisão de marca e identificadores.

**Não fazer:** lançamento comercial sem parecer; tratar parecer como implementação; prometer escrow sem fornecedor contratado.

**Aceite:** pareceres registrados; contratos e termos aprovados; retenção e bases legais documentadas; NFS-e e CPF com fluxo definido; custódia C contratada ou bloqueio declarado.

## Fase 19B — Hardening final e lançamento comercial

**Status:** não iniciada. Depende de 19A, 14B e 15.

**Escopo:** hardening completo (segurança, carga, observabilidade, alertas), LGPD integral, backups/restauração testados, rollout controlado dos módulos comerciais, operação de incidentes e limites de custo.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes; lançamento comercial sem revisão jurídica concluída; ativar pagamento integrado sem PSP contratado e fluxo de NFS-e operacional.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo definidos; revisão legal concluída; piloto comercial monitorado.

## Regra para abrir uma fase

Criar `harness/build/phase-NN-nome.md` contendo objetivo, escopo, exclusões, arquivos esperados, riscos, plano Red/Green/Refactor/Verify, comandos de teste reais, critérios observáveis, evidências e condição de parada. A fase só começa quando o usuário a solicitar explicitamente.
