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
| 12 | Quadras, agenda e KYC | Espaços, agenda, preços, bloqueios e onboarding/KYC do recebedor | 11 |
| 13 | Reservas e temporizadores | Solicitação, aceite, bloqueio, T1/T2/T3, substituição e máquina de estados | 12 |
| 14 | Pagamentos Pix e reembolsos | PSP, cobrança por compra, webhooks, ledger, estorno parcial e repasse | 13 |
| 14D | Ingresso, carteira e temporada | Pacotes e passe, tabela 2D, carteira de ingressos, XP, trilha e catálogo cosmético | 12, 14 |
| 15 | Interface financeira e conciliação | Extrato, repasses a receber, contestação e conciliação do estabelecimento | 14, 14D |
| 16 | Clãs e troféus | Clãs abertos/fechados, chat de clã, troféus por modalidade e temporadas | 8 |
| 17 | Moderação e Trust & Safety | Denúncias de perfil, análise contextual, medidas e revisão humana | 9, 16 |
| 18 | Publicidade | Quadras, estabelecimentos e marcas patrocinados, sem efeito competitivo | 13, 15 |
| 19 | Hardening final e lançamento comercial | Hardening completo, LGPD, revisão jurídica e go-live comercial | 10–18 |

> **Escopo do MVP.** Clãs e troféus (**Fase 16**) passam a integrar o MVP e são pré-requisito do primeiro evento de marketing, conforme a **ADR 0044**. A fase pode rodar em paralelo com as Fases 11 a 15, mantendo a dependência técnica da Fase 8, e precisa estar concluída antes da Fase 19.

> **Reescopo pelo ingresso.** As fases 11–15 foram desenhadas para **reserva paga por participante**. A ADR 0042 mudou três objetos — a cobrança, o reembolso e o recebedor — e a Fase **14D** concentra o modelo novo. O impacto fase a fase está em `docs/PENDENCIAS.md`, seção "Reescopo das Fases 11–15".

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

**Status:** implementada no backend e validada com PostgreSQL 16/PostGIS local em 2026-11-06, sem MMR, sem telas e sem painel; pendente de revisão e commit.

**Escopo:** relatos autorizados com três resultados possíveis (equipe A, equipe B ou empate esportivo quando o formato permitir), janela de 10 minutos controlada pelo backend, quórum `ceil(elegíveis/2)`, resultado por maioria simples, evidência textual privada de até 2.000 caracteres, divergências, segunda rodada de 5 minutos em empate na primeira posição ou divergência exata de 50%, análise interna, revisão humana por CLI/script auditável e decisão registrada. Inclui o desempate de resultado exatamente em 50%: segunda confirmação com histórico preservado e, persistindo o empate, análise interna avaliada relato a relato (sem média de grupo, com capitães como sinal sem peso automático), revisão humana quando inseguro, anulação como último recurso e MMR congelado durante todo o processo (conceito §9.4; ADRs 0008 e 0023).

**Decisões já aprovadas:** não existe tolerância separada de “1–2 votos”; a regra é o limite de 50% sobre votos válidos — abaixo de 50% finaliza, exatamente 50% abre segunda rodada, acima de 50% abre disputa. Votos ausentes ou anulados não entram no denominador. A segunda rodada apresenta todas as alternativas permitidas pelo formato e não há terceira rodada. O capitão da Fase 7 é provisório: maior número de partidas válidas concluídas (`FINALIZED`) do mesmo formato, anteriores à partida atual, e, em empate, UUID; sem critério de nível; seleção na formação e não retroativa. Evidência é apenas textual, privada, com limite de 2.000 caracteres e uma por participante por disputa. A fase é backend-only e não implementa nem atualiza MMR. A CLI exige operador autorizado e motivo.

**Não fazer:** aplicar MMR antes de resultado final; majority vote como antifraude universal; sobrescrever relatos antigos; tornar visível aos participantes a análise interna de confiabilidade; criar telas mobile; implementar upload de arquivos; criar painel administrativo completo; alterar capitães ou resultados históricos.

**Aceite:** resultados conflitantes entram em disputa; partida disputada não altera rating; evidências têm limites de formato/tamanho/acesso; decisão é auditável; três resultados são tratados corretamente; quórum e votos ausentes/anulados são respeitados; segunda rodada tem prazo próprio e alternativas definidas; capitão provisório é determinístico e registrado; contrato HTTP e códigos de erro implementados conforme o plano.

**Pontos abertos após a implementação:** revisar a retenção provisória do ADR 0024 na fase de LGPD; configurar a lista de operadores autorizados da CLI (`JOGA_REVIEW_OPERATORS`). Ver ADR 0023, ADR 0024 e `harness/build/phase-07-resultados-e-disputas.md`.

## Fase 8 — Sistema competitivo

**Status:** implementada no backend e no mobile em 2026-11-06, sem MMR bruto exposto e sem painel administrativo; pendente de revisão/commit final.

**Escopo:** rating inicial simples/versionado, histórico append-only, ranking e Trust Factor separado.

**Não fazer:** rating editável pelo cliente ou painel; apagar histórico; denúncia isolada gerar punição definitiva.

**Aceite:** aplicação única por partida/versão; correções compensatórias; simulações do algoritmo; casual não altera rating ranqueado; contestação e auditoria para sinais de confiança.

## Fase 9 — Comunicação em tempo real

**Status:** 9A, 9B e 9C implementados em 2026-11-06 (backend + mobile + retenção provisória).

**Escopo:** WebSocket autenticado e autorizado, Outbox transacional, push por adaptadores, gestão de tokens de dispositivo, reconciliação de notificações, lista de amigos com convites a lobbies, bloqueios e limites contra spam.

**Não fazer:** conexões em memória como mecanismo de coordenação entre processos; confiar em evento entregue como prova de estado; chat global universal; envio livre de mídia.

**Aceite:** reconnect recupera estado via API; evento duplicado não duplica efeito; sessões expiradas/revogadas perdem acesso; falha push/WebSocket não corrompe a partida; convite de lobby respeita bloqueio, privacidade e limites.

## Fase 10 — Hardening e piloto (núcleo esportivo)

**Status:** 10A (hardening backend local) concluído em 2026-11-06; piloto real pendente.

**Escopo:** threat modeling atualizado, testes de segurança, carga, observabilidade, alertas, backups e restauração, política de retenção, revisão LGPD, rollout controlado do núcleo esportivo. O hardening final, a revisão LGPD completa e o lançamento dos módulos comerciais ocorrem na Fase 19.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo de SMS/maps/infra definidos; piloto monitorado.

## Fase 11 — Organizações e painel de gestão

**Status:** 11A (fundação backend), 11B (painel web) e 11C (CSP, testes de UI e observabilidade) implementados e validados localmente em 2026-11-06/07; sem deploy e sem merge.

**Escopo:** organizações/estabelecimentos esportivos, membros, papéis e permissões por recurso; painel web responsivo autenticado (JOGA y GESTÃO) com cadastro e consulta das operações originadas no JOGA; auditoria de ações administrativas. Framework web registrado em ADR próprio.

**Não fazer:** expor o painel a consumidores; permitir acesso a dados de outra organização; substituir ERP; iniciar reservas pagas, pagamentos, clãs ou publicidade; criar catálogo ou estoque de produtos.

**Aceite:** membro de um estabelecimento não consegue ler nem alterar recursos de outro (testes BOLA/cruzados); papéis respeitados por ação; contratos HTTP versionados com schemas explícitos; identidade compartilhada com o app sem criar conta separada por papel.

## Fase 12 — Quadras, agenda e KYC

**Status:** 12A (quadras, fotos e agenda) implementada e validada localmente em 2026-11-07; 12B (cadastro do estabelecimento como fornecedor e chave de repasse) pendente.

**Escopo 12A — quadras, fotos e agenda:** cadastro de espaços/quadras, **faixa de preço com atributo visível e teto de valor (ADR 0042 §9)**, vínculo esporte–quadra, fotos de quadra com upload autenticado por organização, revisão, armazenamento privado, remoção e retenção; agenda, preços, intervalos, bloqueios, exceções e registro de reservas externas para evitar conflito; ligação entre o catálogo `venues` da Fase 4 e o perfil comercial `organization_venues` da Fase 11.

**Escopo 12B — fornecedor e repasse:** dados cadastrais do estabelecimento, chave Pix ou conta bancária de titularidade do próprio CNPJ, contrato de intermediação com teto de valor por faixa e regra que impede reserva paga sem chave de repasse validada. Não há KYC de recebedor de marketplace: a quadra é fornecedora, paga por Pix.

**Não fazer:** exigir integração ERP/PDV; implementar logística, produtos ou estoque; permitir reserva paga para recebedor em credenciamento; representar espaço público como reservável sem autorização verificável; aceitar foto de pessoa, upload livre ou URL arbitrária; publicar foto sem revisão.

**Aceite:** dois usuários não reservam o mesmo intervalo; constraints e transações protegem sobreposição; agenda respeita fuso e duração do formato; KYC pendente bloqueia a abertura de cobrança; estados do recebedor são consultáveis e auditáveis; estabelecimento só acessa a própria agenda; foto só é exibida após revisão e vínculo com organização ativa; membro de outra organização não lê, envia, revisa nem remove foto; remoção e retenção são auditáveis.

## Fase 13 — Reservas e temporizadores

**Status:** 13A (backend de reservas, holds e T1/T2/T3) e 13B (painel mobile de reservas e ajustes de painel) implementados e validados localmente em 2026-11-07; criação automática a partir do lobby, T2 em horário comercial e pagamentos reais pendentes.

**Escopo:** solicitação de reserva ao estabelecimento, aceite/recusa, bloqueio temporário do espaço específico, T1 (confirmação de participação), T2 (resposta do estabelecimento), T3 (bloqueio e confirmação do acesso), expiração, substituição de participantes, cancelamento antes da confirmação, origem `JOGA` e máquina de estados auditável. **No fluxo de ingresso não há cobrança na reserva:** o ingresso é consumido na confirmação (ADR 0042). O fluxo de reserva avulsa mantém a cobrança por participante.

**Não fazer:** abrir cobrança antes do aceite e do bloqueio; confirmar reserva sem todos os pagamentos no fluxo avulso ou sem saldo no fluxo de ingresso; permitir transição livre por endpoint; prorrogar bloqueio ou reiniciar prazo na substituição; cobrar comissão de reserva externa sem acordo explícito.

**Aceite:** dois usuários não bloqueiam o mesmo intervalo; timers controlados pelo backend e idempotentes; substituição não duplica vaga nem cobrança; no fluxo avulso a reserva não confirma com pagamento incompleto e no fluxo de ingresso não confirma sem saldo suficiente; usuário só atua em reservas das quais participa; matriz de transições válidas/inválidas testada.

## Fase 14 — Pagamentos Pix e reembolsos

**Status:** 14A (Mercado Pago sandbox, Pix, webhook e ledger) e 14C (reembolsos, extrato e conciliação com PSP simulado) implementadas e validadas localmente em 2026-11-07; 14B (Inter PJ em produção, Pix, estorno parcial e repasse) pendente.

**Escopo:** integração com PSP, uma cobrança Pix por compra de pacote ou passe; Mercado Pago no protótipo/beta e **Inter PJ em produção**; webhooks autenticados e idempotentes; ledger financeiro interno auditável; estorno parcial de Pix para os 7 dias do CDC; repasse ao estabelecimento em `starts_at + 2h` (ADR 0040); conciliação básica. O fluxo de ingresso segue a ADR 0042 e não usa split nem recebedor de marketplace.

**Não fazer:** construir processador próprio ou carteira custodial; armazenar dados completos de cartão; confiar no retorno visual do app; abrir cobrança antes do bloqueio; liberar valor ao estabelecimento antes da confirmação; deduzir tarifas do reembolso do jogador.

**Aceite:** status financeiro só muda por evento autenticado ou consulta server-to-server; replay de webhook não duplica pagamento, vaga ou reembolso; reembolso devolve principal e taxa; cobrança de participante substituído vai para reembolso; ledger e PSP permanecem conciliáveis; autorização negativa entre reservas testada.

## Fase 14D — Ingresso, carteira e temporada

**Status:** fatias **14D.1 a 14D.5** implementadas em 2026-11-12. A quitação por ingresso usa o modelo A (cada participante debita o próprio saldo). Falta devolução em ingresso no cancelamento (14D.6).

**Depende de:** 12 (faixas de preço e fornecedor) e 14 (PSP e ledger). Alimenta as Fases 15, 16 e 19.

**Escopo:** ingresso como unidade de acesso pré-paga; pacotes com escada de preço (3/10/30/50) e passe trimestral com franquia mensal; tabela 2D formato × faixa, versionada e congelada na reserva; consumo na confirmação e devolução em ingresso conforme a ADR 0039; carteira com três buckets (custeio, faturamento e margem) e provisão de 100% do passivo; XP em ledger append-only; trilha de 30 níveis, missões semanais, streak de vitórias e nível de temporada; catálogo cosmético em três estados, com atribuição e revogação de itens de passe; ingressos grátis por nível; inteligência de rede; crédito de estreia.

**Não fazer:** recorrência automática ou Pix Automático; transferência, revenda ou saque de ingresso; validade para ingresso comprado; lançar rendimento de float ou breakage como receita; mapa de calor de evento de jogo; qualquer item que altere MMR, Trust Factor, matchmaking ou troféu de clã.

**Aceite:** compra idempotente por chave; consumo idempotente por reserva; devolução em ingresso conforme a matriz da ADR 0039; tabela versionada e gravada na reserva; XP sem duplicidade por `ref_id`; nível e atribuição reconstruíveis a partir do ledger; item de passe revogado ao fim do ciclo; nenhum item altera competitividade; ledger conciliável com o PSP; painel de passivo e cobertura de caixa.

## Fase 15 — Interface financeira e conciliação

**Status:** 15A (liberações, contestações, extrato, recebíveis e conciliação interna) e 15B (aba Financeiro do painel) implementados como **proposta técnica local** em 2026-11-09. A ADR 0039 define a política consolidada de cancelamento, substituição, presença e ausência e supera a ADR 0038. A ADR 0038 foi revertida e as fatias 1–6 da 0039 (fila, chamada automática, cancelamento individual, T4/T5, reembolso sem o desistente, atribuição/pagamento, vaga paga em no-show, presença T6–T9, coordenadas obrigatórias e recomendação de formação) estão implementadas. A ADR 0040 define o repasse 2 h após o início da partida. A ADR 0041 implementa o Trust Factor interno (penalidades, recuperação e restrição ranqueada). UI de presença/suporte continua pendente. Nenhuma decisão de prazo, repasse, moderação financeira ou tratamento de divergência foi aprovada; PSP real, MED/chargeback, comprovantes fiscais, KYC e os três relógios (pagamento, contestação e repasse) continuam pendentes.

**Escopo:** interface financeira do estabelecimento com extrato por reserva e por repasse, agenda de repasses a receber, status de repasse, comprovantes, dados contratuais, canal de contestação e histórico de estornos; **repasse em `starts_at + 2h`** (ADR 0040); conciliação periódica; tratamento de MED, chargeback e estorno sem saldo; obrigações de transparência aplicáveis (Res. 264/349). O fluxo de ingresso não usa split nem recebedor: o estabelecimento é fornecedor e recebe por Pix.

**Não fazer:** repassar antes da confirmação; esconder taxas ou ajustes; transformar a interface em ERP; executar ajuste manual irreversível sem justificativa e auditoria; tratar repasse como garantia automática contra MED.

**Aceite:** repasse idempotente e registrado no ledger; extrato do estabelecimento bate com o PSP; contestação tem prazo, canal e decisão auditável; estabelecimento só vê os próprios dados; relatório de repasses reproduzível; eventos de MED e estorno sem saldo registrados e tratados.

## Fase 16 — Clãs e troféus

**Status:** antecipada para o **escopo do MVP** pela ADR 0044. Pode rodar em paralelo às Fases 11 a 15, mantendo a dependência da Fase 8, e deve estar concluída antes do primeiro evento de marketing e antes da Fase 19. Uma fatia mínima de moderação de chat de clã entra junto com esta fase.

**Escopo:** clãs abertos/fechados com membros, administradores, convites e limites; chat de clã em texto e referências internas; vínculo clã–jogador na data de cada partida; troféus por modalidade com fórmula-base 50/30/20 versionada, considerando os 10 melhores membros elegíveis, temporadas configuráveis e snapshots; ciclo de moderação do chat segue a Fase 17.

**Não fazer:** aceitar pontos enviados pelo cliente; permitir compra, pagamento ou publicidade de pontos; somar modalidades em um ranking único; implementar ranking público sem simulação e testes de abuso.

**Aceite:** mudança de clã não transfere troféus retroativos; participação tem limites contra volume artificial; elegibilidade exige permanência mínima; temporada encerra com snapshot auditável; chat de clã acessível só a membros autorizados.

## Fase 17 — Moderação e Trust & Safety

**Escopo:** denúncia de perfil no lobby com categorias definidas e seleção de até cinco mensagens + janela limitada de contexto; moderação assistida por IA (classificação, agrupamento, priorização, medidas preventivas proporcionais e reversíveis, níveis de confiança); revisão humana em ferramenta interna separada do painel de gestão; recursos contra penalizações; histórico auditável de decisões; retenção e acesso limitados.

**Não fazer:** moderação de mídia enviada por usuários (o MVP não tem upload livre em perfil, lobby ou chat); moderação de fotos de quadra, que tem fluxo próprio na Fase 12; suspensão permanente definida apenas por IA; denúncia isolada reduzir Trust Factor; encaminhar toda conversa continuamente para análise.

**Aceite:** só participantes do lobby denunciam e só mensagens da própria conversa podem ser anexadas; medidas proporcionais com justificativa, reversibilidade das automáticas e possibilidade de contestação; acesso a conteúdo de moderação restrito a funções autorizadas e registrado.

## Fase 18 — Publicidade

**Escopo:** estabelecimentos e quadras em destaque, campanhas de marcas, identificação visual de anúncios, registros de impressão/clique/conversão com minimização de dados e LGPD.

**Não fazer:** alterar MMR, Trust Factor, matchmaking, composição de equipes ou rankings por pagamento; violar filtros do usuário; tratar publicidade como receita antes de audiência; criar catálogo ou venda de produtos.

**Aceite:** posições patrocinadas identificadas; filtros obrigatórios respeitados; métricas auditáveis e sem dados desnecessários; completude comercial documentada antes do go-live.

## Fase 19 — Hardening final e lançamento comercial

**Escopo:** hardening completo (segurança, carga, observabilidade, alertas), LGPD integral (retenção de mensagens, eventos, dados financeiros e exclusão de contas), revisão jurídica do modelo de split/custódia, KYC, condições comerciais e política de cancelamento, backups/restauração testados, rollout controlado dos módulos comerciais.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes; lançamento comercial sem revisão jurídica concluída; ativar pagamento integrado sem PSP contratado e KYC operacional.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo definidos; revisão legal concluída; piloto comercial monitorado.

## Regra para abrir uma fase

Criar `harness/build/phase-NN-nome.md` contendo objetivo, escopo, exclusões, arquivos esperados, riscos, plano Red/Green/Refactor/Verify, comandos de teste reais, critérios observáveis, evidências e condição de parada. A fase só começa quando o usuário a solicitar explicitamente.
