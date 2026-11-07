# Pendências abertas do JOGA

**Atualizado em:** 7 de novembro de 2026

Este arquivo consolida o que ficou aberto após as Fases 11–14C. Não substitui `PLANS.md`, os ADRs nem os arquivos de fase; serve como painel de acompanhamento.

## Bloqueios externos

| Pendência | Fase | Impacto | Próximo passo |
|---|---|---|---|
| PSP de produção (Pagar.me) | 14B | Sem split, retenção, estorno real e conciliação | Contratar/validar PSP, credenciais e contrato |
| KYC do recebedor | 12B | Reserva paga não pode abrir sem recebedor `ACTIVE` | Decidir PSP/KYC e onboarding |
| SMS real | 10/19 | Login real depende de OTP | Escolher provedor, custo, antiabuso e LGPD |
| Push real | 10/19 | Notificações de prazo e resultado | Configurar APNs/FCM e credenciais |
| Mapas | 10/19 | Camada visual de descoberta | Pode esperar; usar lista/distância no início |
| CNPJ/MEI e revisão jurídica | 14B/19 | Dinheiro real e contratos | Definir entidade, contador e parecer jurídico |
| Storage de fotos de produção | 12A/19 | Fotos privadas e retenção | Escolher storage, criptografia e backup |

## Pendências de produto e engenharia

| Pendência | Fase | Estado |
|---|---|---|
| T2 em horário comercial | 14B | Hoje usa tempo corrido; falta calendário, feriados e dias fechados |
| T3 configurável por estabelecimento | 13B/14B | Hoje usa configuração global |
| Política de cancelamento após confirmação | 14B/15 | Reembolso integral no beta; produção pendente |
| Reembolso real, MED e chargeback | 14B/15 | Apenas simulado |
| Conciliação periódica com PSP | 15 | Apenas ledger interno |
| Liberação automática após `N` horas | 15 | `N` ainda não definido; hoje o repasse é simulado/manual após `COMPLETED` |
| Janela de disputa antes da liberação | 15 | Pendente |
| Extrato/recibos/comprovantes reais | 15 | Resumo e extrato internos já existem |
| Interface financeira completa do estabelecimento | 15 | Em andamento |
| Jornada mobile completa de reserva/quadra | 13B | Painel de acompanhamento existe; falta seletor de quadra e criação |
| Revisão independente de fotos | 17 | Revisão inicial é feita pela organização |
| Catálogo de avatares | 17 | Decisão registrada; implementação pendente |
| Kit da partida | 5/6/13 | Decisão registrada; implementação pendente |
| Catálogo definitivo de equipamento | 13/17 | Pendente |
| Redirecionamento de quadra em recusa/expiração | 14B | Pendente |
| Limite de substituições | 14B | Pendente |
| `p_t` dinâmico por Trust Factor | 15/17 | Hipótese registrada na ADR 0036; não aprovada |
| Score de risco de pagamento | 15/17 | Só após dados reais de MED/chargeback |
| Integração da conclusão com o ciclo da partida | 15 | Hoje é ação operacional do estabelecimento |
| Testes de UI mobile | 19 | Ainda manuais |
| LGPD e retenção definitiva | 19 | Revisão jurídica pendente |

## Dívidas técnicas conhecidas

- `MercadoPagoAdapter` usa sandbox e não deve operar dinheiro real.
- O webhook real depende de URL pública/túnel e segredo configurado no painel.
- O e-mail do pagador é obrigatório na Orders API; o cadastro atual é por telefone.
- O adaptador de produção (Pagar.me) ainda não existe.
- O repasse ao estabelecimento é um lançamento simulado no ledger; não há transferência real.
- O worker de reservas reembolsa com o adaptador configurado; se o PSP real falhar, a operação precisa de retry e conciliação.
- A interface financeira ainda não tem comprovantes, contestação e exportação.

## Regra de avanço

- Não iniciar 14B sem PSP/contrato e autorização.
- Fase 15 pode avançar sobre o ledger simulado, sem prometer repasse real.
- Fases 16–18 exigem autorização específica e registro em `PLANS.md`.
- Qualquer mudança de dinheiro real, custódia, KYC ou retenção exige ADR e revisão jurídica.
