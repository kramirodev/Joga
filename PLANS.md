# Roadmap de desenvolvimento — Esporte Vivo

Este roadmap define dependências e critérios de saída. Cada fase deve ganhar um arquivo próprio em `harness/build/` antes da implementação. Não executar várias fases com um único pedido ao Codex.

## Visão geral

| Fase | Nome | Objetivo de saída | Dependência |
|---|---|---|---|
| 0 | Repositório e governança | Repositório V2 protegido, documentação e fluxo de trabalho definidos | Nenhuma |
| 1 | Prova técnica mobile/nativa | Build Android/iOS e provas de passkey, localização e integrações críticas | 0 |
| 2 | Fundação de engenharia | Esqueletos mobile/backend, ambiente local, CI e health checks | 1 |
| 3 | Identidade e segurança | Cadastro por telefone, OTP, passkeys, sessões e recuperação segura | 2 |
| 4 | Perfil e descoberta | Perfil esportivo, modalidades, disponibilidade, locais e busca manual/GPS | 3 |
| 5 | Filas e matchmaking | Filas persistentes, worker e formação idempotente de partidas | 4 |
| 6 | Ciclo de partidas | Confirmação, presença, expiração e máquina de estados | 5 |
| 7 | Resultados e disputas | Relatos, divergência, evidências e resolução auditável | 6 |
| 8 | Competitivo | MMR versionado, ranking e Trust Factor separados | 7 |
| 9 | Comunicação em tempo real | WebSocket autorizado, Outbox, push e reconciliação | 6; integra 8 quando aplicável |
| 10 | Hardening e piloto | Segurança, carga, observabilidade, backup/restore e lançamento controlado | 3–9 |

## Fase 0 — Repositório e governança

**Escopo:** preservar a implementação antiga; decidir novo repositório ou branch `rebuild/v2`; adicionar os arquivos de governança; definir `main` estável e branches curtas; preparar documentação e templates de PR.

**Não fazer:** implementar endpoints, telas, tabelas de negócio, autenticação ou matchmaking.

**Aceite:** arquivos `AGENTS.md`, `GOALS.md`, `PLANS.md`, `PROMPTS.md` e documentação técnica estão no lugar; README explica como iniciar; `git diff --check` passa; projeto antigo permanece recuperável; nenhuma credencial é adicionada.

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

**Escopo:** relatórios autorizados, evidências privadas, divergências, disputa e decisão registrada.

**Não fazer:** aplicar MMR antes de resultado final; majority vote como antifraude universal; sobrescrever relatos antigos.

**Aceite:** resultados conflitantes entram em disputa; partida disputada não altera rating; evidências têm limites de formato/tamanho/acesso; decisão é auditável.

## Fase 8 — Sistema competitivo

**Escopo:** rating inicial simples/versionado, histórico append-only, ranking e Trust Factor separado.

**Não fazer:** rating editável pelo cliente ou painel; apagar histórico; denúncia isolada gerar punição definitiva.

**Aceite:** aplicação única por partida/versão; correções compensatórias; simulações do algoritmo; casual não altera rating ranqueado; contestação e auditoria para sinais de confiança.

## Fase 9 — Comunicação em tempo real

**Escopo:** WebSocket autenticado e autorizado, Outbox transacional, push por adaptadores, gestão de tokens de dispositivo e reconciliação de notificações.

**Não fazer:** conexões em memória como mecanismo de coordenação entre processos; confiar em evento entregue como prova de estado.

**Aceite:** reconnect recupera estado via API; evento duplicado não duplica efeito; sessões expiradas/revogadas perdem acesso; falha push/WebSocket não corrompe a partida.

## Fase 10 — Hardening e piloto

**Escopo:** threat modeling atualizado, testes de segurança, carga, observabilidade, alertas, backups e restauração, política de retenção, revisão LGPD, rollout controlado.

**Não fazer:** produção sem plano de rollback, backup restaurável, alertas e responsável por incidentes.

**Aceite:** evidências de testes documentadas; restore testado; vulnerabilidades críticas/altas resolvidas ou formalmente bloqueadoras; limites de custo de SMS/maps/infra definidos; piloto monitorado.

## Regra para abrir uma fase

Criar `harness/build/phase-NN-nome.md` contendo objetivo, escopo, exclusões, arquivos esperados, riscos, plano Red/Green/Refactor/Verify, comandos de teste reais, critérios observáveis, evidências e condição de parada. A fase só começa quando o usuário a solicitar explicitamente.
