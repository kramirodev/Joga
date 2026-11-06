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
| 14 | Pagamentos Pix e reembolsos | PSP, cobranças individuais, split/custódia, webhooks, ledger e reembolsos | 13 |
| 15 | Interface financeira e conciliação | Extrato, recebíveis, liberação, contestação e conciliação do estabelecimento | 14 |
| 16 | Clãs e troféus | Clãs abertos/fechados, chat de clã, troféus por modalidade e temporadas | 8 |
| 17 | Moderação e Trust & Safety | Denúncias de perfil, análise contextual, medidas e revisão humana | 9, 16 |
| 18 | Publicidade | Quadras, estabelecimentos e marcas patrocinados, sem efeito competitivo | 13, 15 |
| 19 | Hardening final e lançamento comercial | Hardening completo, LGPD, revisão jurídica e go-live comercial | 10–18 |

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

**Escopo:** rating inicial simples/versionado, histórico append-only, ranking e Trust Factor separado.

**Não fazer:** rating editável pelo cliente ou painel; apagar histórico; denúncia isolada gerar punição definitiva.

**Aceite:** aplicação única por partida/versão; correções compensatórias; simulações do algoritmo; casual não altera rating ranqueado; contestação e auditoria para sinais de confiança.

## Fase 9 — Comunicação em tempo real

**Escopo:** WebSocket autenticado e autorizado, Outbox transacional, push por adaptadores, gestão de tokens de dispositivo, reconciliação de notificações, lista de amigos com convites a lobbies, bloqueios e limites contra spam.

**Não fazer:** conexões em memória como mecanismo de coordenação entre processos; confiar em evento entregue como prova de estado; chat global universal; envio livre de mídia.

**Aceite:** reconnect recupera estado via API; evento duplicado não duplica efeito; sessões expiradas/revogadas perdem acesso; falha push/WebSocket não corrompe a partida; convite de lobby respeita bloqueio, privacidade e limites.

## Fase 10 — Hardening e piloto (núcleo esportivo)

**Escopo:** threat modeling atualizado, testes de segurança, carga, observabilidade, alertas, backups e restauração, política de retenção, revisão LGPD, rollout controlado do núcleo esportivo. O hardening final, a revisão LGPD completa e o lançamento dos módulos comerciais ocorrem na Fase 19.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo de SMS/maps/infra definidos; piloto monitorado.

## Fase 11 — Organizações e painel de gestão

**Escopo:** organizações/estabelecimentos esportivos, membros, papéis e permissões por recurso; painel web responsivo autenticado (JOGA y GESTÃO) com cadastro e consulta das operações originadas no JOGA; auditoria de ações administrativas. Framework web registrado em ADR próprio.

**Não fazer:** expor o painel a consumidores; permitir acesso a dados de outra organização; substituir ERP; iniciar reservas pagas, pagamentos, clãs ou publicidade; criar catálogo ou estoque de produtos.

**Aceite:** membro de um estabelecimento não consegue ler nem alterar recursos de outro (testes BOLA/cruzados); papéis respeitados por ação; contratos HTTP versionados com schemas explícitos; identidade compartilhada com o app sem criar conta separada por papel.

## Fase 12 — Quadras, agenda e KYC

**Escopo:** cadastro de espaços/quadras, vínculo esporte–quadra, agenda, preços, intervalos, bloqueios, exceções e registro de reservas externas para evitar conflito; onboarding do estabelecimento como recebedor no PSP, com dados cadastrais, conta bancária na mesma titularidade e validação de identidade/KYC; estados do recebedor e regra que impede reserva paga sem recebedor ativo.

**Não fazer:** exigir integração ERP/PDV; implementar logística, produtos ou estoque; permitir reserva paga para recebedor em credenciamento; representar espaço público como reservável sem autorização verificável.

**Aceite:** dois usuários não reservam o mesmo intervalo; constraints e transações protegem sobreposição; agenda respeita fuso e duração do formato; KYC pendente bloqueia a abertura de cobrança; estados do recebedor são consultáveis e auditáveis; estabelecimento só acessa a própria agenda.

## Fase 13 — Reservas e temporizadores

**Escopo:** solicitação de reserva ao estabelecimento, aceite/recusa, bloqueio temporário do espaço específico, T1 (confirmação de participação), T2 (resposta do estabelecimento), T3 (bloqueio e pagamento), expiração, substituição de participantes, cancelamento antes da confirmação, origem `JOGA` e máquina de estados auditável.

**Não fazer:** abrir cobrança antes do aceite e do bloqueio; confirmar reserva sem todos os pagamentos; permitir transição livre por endpoint; prorrogar bloqueio ou reiniciar prazo na substituição; cobrar comissão de reserva externa sem acordo explícito.

**Aceite:** dois usuários não bloqueiam o mesmo intervalo; timers controlados pelo backend e idempotentes; substituição não duplica vaga nem cobrança; reserva não confirma com pagamento incompleto; usuário só atua em reservas das quais participa; matriz de transições válidas/inválidas testada.

## Fase 14 — Pagamentos Pix e reembolsos

**Escopo:** integração com PSP, um `order` por reserva e uma cobrança Pix por participante; split por cobrança ou custódia centralizada conforme decisão do ADR 0021; webhooks autenticados e idempotentes; ledger financeiro interno auditável; estados financeiros individuais; reembolso integral quando a reserva não se completa; pagamentos tardios; conciliação básica.

**Não fazer:** construir processador próprio ou carteira custodial; armazenar dados completos de cartão; confiar no retorno visual do app; abrir cobrança antes do bloqueio; liberar valor ao estabelecimento antes da confirmação; deduzir tarifas do reembolso do jogador.

**Aceite:** status financeiro só muda por evento autenticado ou consulta server-to-server; replay de webhook não duplica pagamento, vaga ou reembolso; reembolso devolve principal e taxa; cobrança de participante substituído vai para reembolso; ledger e PSP permanecem conciliáveis; autorização negativa entre reservas testada.

## Fase 15 — Interface financeira e conciliação

**Escopo:** interface financeira do estabelecimento com extrato por reserva e cobrança, agenda de recebíveis, status de liberação, comprovantes, dados contratuais, canal de contestação e histórico de estornos; liberação do valor somente depois da confirmação da reserva e da realização da partida; liberação automática após `N` horas, com janela de disputa; conciliação periódica; tratamento de MED, chargeback e estorno sem saldo; obrigações de transparência aplicáveis (Res. 264/349).

**Não fazer:** liberar antes da confirmação; esconder taxas ou ajustes; transformar a interface em ERP; executar ajuste manual irreversível sem justificativa e auditoria; tratar saldo do recebedor como garantia automática contra MED.

**Aceite:** liberação idempotente e registrada no ledger; extrato do estabelecimento bate com o PSP; contestação tem prazo, canal e decisão auditável; estabelecimento só vê os próprios dados; relatório de recebíveis reproduzível; eventos de MED e estorno sem saldo registrados e tratados.

## Fase 16 — Clãs e troféus

**Escopo:** clãs abertos/fechados com membros, administradores, convites e limites; chat de clã em texto e referências internas; vínculo clã–jogador na data de cada partida; troféus por modalidade com fórmula-base 50/30/20 versionada, considerando os 10 melhores membros elegíveis, temporadas configuráveis e snapshots; ciclo de moderação do chat segue a Fase 17.

**Não fazer:** aceitar pontos enviados pelo cliente; permitir compra, pagamento ou publicidade de pontos; somar modalidades em um ranking único; implementar ranking público sem simulação e testes de abuso.

**Aceite:** mudança de clã não transfere troféus retroativos; participação tem limites contra volume artificial; elegibilidade exige permanência mínima; temporada encerra com snapshot auditável; chat de clã acessível só a membros autorizados.

## Fase 17 — Moderação e Trust & Safety

**Escopo:** denúncia de perfil no lobby com categorias definidas e seleção de até cinco mensagens + janela limitada de contexto; moderação assistida por IA (classificação, agrupamento, priorização, medidas preventivas proporcionais e reversíveis, níveis de confiança); revisão humana em ferramenta interna separada do painel de gestão; recursos contra penalizações; histórico auditável de decisões; retenção e acesso limitados.

**Não fazer:** moderação de mídias (não há upload no escopo); suspensão permanente definida apenas por IA; denúncia isolada reduzir Trust Factor; encaminhar toda conversa continuamente para análise.

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
