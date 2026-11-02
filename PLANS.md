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
| 11 | Organizações e gestão web | Organizações, membros, papéis, isolamento e painel web (JOGA y GESTÃO) | 3 |
| 12 | Catálogo e estoque comprometido | Produtos, variantes e estoque alocado ao canal JOGA com movimentações auditáveis | 11 |
| 13 | Pedidos, pagamentos e cumprimento | PSP, checkout, webhooks, retirada/entrega pelo vendedor, código de recebimento e devoluções | 12 |
| 14 | Quadras e reservas | Espaços, agenda, disponibilidade e reserva paga de quadras privadas (JOGA y QUADRA) | 11 |
| 15 | Integridade comercial | Denúncias de pedidos, conversa comprador-vendedor, disputas comerciais e antifraude | 13 |
| 16 | Clãs e troféus | Clãs abertos/fechados, chat de clã, troféus por modalidade e temporadas | 8 |
| 17 | Moderação e Trust & Safety | Denúncias de perfil, análise contextual, medidas e revisão humana | 9, 16 |
| 18 | Publicidade | Produtos, lojas e quadras patrocinados, sem efeito competitivo | 13 |
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

**Escopo:** relatórios autorizados, evidências privadas, divergências, disputa e decisão registrada. Inclui o desempate de resultado exatamente em 50%: segunda confirmação com histórico preservado e, persistindo o empate, análise interna de confiabilidade avaliada relato a relato (sem média de grupo, com capitães como sinal sem peso automático), revisão humana quando inseguro, anulação como último recurso e MMR congelado durante todo o processo (conceito §9.4; ADR 0008).

**Não fazer:** aplicar MMR antes de resultado final; majority vote como antifraude universal; sobrescrever relatos antigos; tornar visível aos participantes a análise interna de confiabilidade.

**Aceite:** resultados conflitantes entram em disputa; partida disputada não altera rating; evidências têm limites de formato/tamanho/acesso; decisão é auditável.

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

## Fase 11 — Organizações e gestão web

**Escopo:** organizações/estabelecimentos, membros, papéis e permissões por recurso, perfis de loja (JOGA y LOJA) e de quadras (JOGA y QUADRA) vinculados à organização, painel web responsivo autenticado (JOGA y GESTÃO) com cadastro e consulta das operações originadas no JOGA, auditoria de ações administrativas. Framework web registrado em ADR próprio.

**Não fazer:** expor o painel a consumidores; permitir acesso a dados de outra organização; substituir ERP; iniciar marketplace, reservas pagas ou clãs.

**Aceite:** membro de uma loja não consegue ler nem alterar recursos de outra (testes BOLA/cruzados); papéis respeitados por ação; contratos HTTP versionados com schemas explícitos; identidade compartilhada com o app sem criar conta separada por papel.

## Fase 12 — Catálogo e estoque comprometido

**Escopo:** produtos, variantes, imagens e preços; quantidade alocada ao canal JOGA (disponível, reservada em checkout, vendida); movimentações auditáveis de entrada, ajuste, reserva, liberação, venda e devolução; holds de checkout transacionais.

**Não fazer:** exigir integração ERP/PDV; implementar logística, frete ou rastreamento; aceitar estoque negativo ou movimentação sem razão registrada.

**Aceite:** dois checkouts concorrentes não vendem além do saldo; hold expirado é liberado de forma idempotente; movimentações e saldo materializado permanecem consistentes; vendedor só consulta/aloca estoque próprio.

## Fase 13 — Pedidos, pagamentos e cumprimento

**Escopo:** checkout com reserva de estoque, PSP com split quando disponível, webhooks autenticados e idempotentes, ledger financeiro interno auditável, retirada e entrega pelo vendedor, código de confirmação de recebimento, cancelamentos, devoluções e reembolsos conforme a legislação aplicável.

**Não fazer:** construir processador próprio ou carteira custodial; armazenar dados completos de cartão; confiar em retorno visual do checkout; gerar custos reais de PSP sem autorização.

**Aceite:** status financeiro oficial só muda por evento autenticado ou consulta server-to-server; replay de webhook não duplica venda/movimentação; código de recebimento é único, armazenado como hash, com limite de tentativas, expiração e evento auditável; pedido não pago não gera cumprimento.

## Fase 14 — Quadras e reservas

**Escopo:** cadastro de estabelecimento/espaços/quadras, agenda, preços, bloqueios, registro de reservas externas para evitar conflito, reserva e pagamento de quadras privadas originados no JOGA, comissão sobre reservas originadas, cancelamento/reembolso e políticas por estabelecimento.

**Não fazer:** representar espaço público como formalmente reservável sem autorização verificável; bloquear intervalos fora de transação; cobrar comissão de reservas externas sem acordo explícito.

**Aceite:** dois usuários não reservam o mesmo intervalo; hold/lock transacional protege conflito de intervalo; origem `JOGA` registrada para comissão; cancelamento/devolução respeitam política e leis aplicáveis.

## Fase 15 — Integridade comercial

**Escopo:** denúncia de transação (tipo, descrição, até três imagens com limites e controles, vínculo automático ao pedido); comunicação comprador-vendedor pré-compra (loja/produto) e pós-compra (pedido), com histórico preservado; propostas de solução e disputas comerciais com fluxo progressivo (coleta automática, classificação por regras/IA, resolução entre as partes, revisão humana, decisão registrada); integração com eventos de pagamento, reembolso e chargeback; proteções antifraude de compradores e vendedores.

**Não fazer:** decisão irreversível de reembolso/penalização automatizada apenas por IA; considerar qualquer parte culpada automaticamente pela abertura de denúncia; deixar denúncia comercial alterar Trust Factor, MMR ou troféus; liberar códigos de recebimento como prova absoluta de conformidade.

**Aceite:** denúncia só pelo comprador/vendedor do pedido; evidências com tipo/tamanho/autorização/retenção controlados e armazenamento privado; conversas idempotentes, paginadas e acessíveis só ao contexto autorizado; decisão com justificativa auditável append-only; código de recebimento com limites de tentativa e expiração, sem contornar controles.

## Fase 16 — Clãs e troféus

**Escopo:** clãs abertos/fechados com membros, administradores, convites e limites; chat de clã em texto e referências internas; vínculo clã–jogador na data de cada partida; troféus por modalidade com fórmula-base 50/30/20 versionada, considerando os 10 melhores membros elegíveis, temporadas configuráveis e snapshots; ciclo de moderação do chat segue a Fase 17.

**Não fazer:** aceitar pontos enviados pelo cliente; permitir compra, pagamento ou publicidade de pontos; somar modalidades em um ranking único; implementar ranking público sem simulação e testes de abuso.

**Aceite:** mudança de clã não transfere troféus retroativos; participação tem limites contra volume artificial; elegibilidade exige permanência mínima; temporada encerra com snapshot auditável; chat de clã acessível só a membros autorizados.

## Fase 17 — Moderação e Trust & Safety

**Escopo:** denúncia de perfil no lobby com categorias definidas e seleção de até cinco mensagens + janela limitada de contexto; moderação assistida por IA (classificação, agrupamento, priorização, medidas preventivas proporcionais e reversíveis, níveis de confiança); revisão humana em ferramenta interna separada dos painéis de loja; recursos contra penalizações; histórico auditável de decisões; retenção e acesso limitados.

**Não fazer:** moderação de mídias (não há upload no escopo); suspensão permanente definida apenas por IA; denúncia isolada reduzir Trust Factor; encaminhar toda conversa continuamente para análise.

**Aceite:** só participantes do lobby denunciam e só mensagens da própria conversa podem ser anexadas; medidas proporcionais com justificativa, reversibilidade das automáticas e possibilidade de contestação; acesso a conteúdo de moderação restrito a funções autorizadas e registrado.

## Fase 18 — Publicidade

**Escopo:** produtos patrocinados, lojas e quadras em destaque, campanhas de marcas, identificação visual de anúncios, registros de impressão/clique/conversão com minimização de dados e LGPD.

**Não fazer:** alterar MMR, Trust Factor, matchmaking, composição de equipes ou rankings por pagamento; violar filtros do usuário; tratar publicidade como receita antes de audiência.

**Aceite:** posições patrocinadas identificadas; filtros obrigatórios respeitados; métricas auditáveis e sem dados desnecessários; completude comercial documentada antes do go-live.

## Fase 19 — Hardening final e lançamento comercial

**Escopo:** hardening completo (segurança, carga, observabilidade, alertas), LGPD integral (retenção de mensagens, eventos, dados financeiros e exclusão de contas), revisão jurídica do marketplace e das condições comerciais, backups/restauração testados, rollout controlado dos módulos comerciais.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes; lançamento comercial sem revisão jurídica concluída.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo definidos; revisão legal concluída; piloto comercial monitorado.

## Regra para abrir uma fase

Criar `harness/build/phase-NN-nome.md` contendo objetivo, escopo, exclusões, arquivos esperados, riscos, plano Red/Green/Refactor/Verify, comandos de teste reais, critérios observáveis, evidências e condição de parada. A fase só começa quando o usuário a solicitar explicitamente.
