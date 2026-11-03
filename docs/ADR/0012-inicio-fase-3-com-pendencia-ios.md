# ADR 0012 — Início da Fase 3 com a pendência iOS da Fase 1

- **Status:** Aprovado pelo responsável do produto em 2026-11-03, ao autorizar o início da Fase 3.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` (Fases 1 e 3), ADR 0010, ADR 0011, `harness/build/phase-01-prova-tecnica-mobile-nativa.md`.

## Contexto

A Fase 1 permanece `In progress`: a associação Android e a cerimônia de passkey foram concluídas, mas iOS/`apple-app-site-association` e o build iOS continuam bloqueados por ausência de conta Apple e macOS/Xcode. A Fase 2 está `Complete` em `489fe8d`.

O `PLANS.md` declara a Fase 3 dependente da Fase 2, mas o critério de aceite da Fase 3 inclui “passkey testada em Android e iOS”. Implementar identidade e segurança agora, sem resolver o iOS, mantém esse critério aberto — o que precisa ser explícito, não silencioso.

## Decisão

1. Iniciar a Fase 3 na branch `feat/03-identidade-e-seguranca`, empilhada sobre a Fase 1 ainda não integrada, sem encerrar a Fase 1.
2. Manter a Fase 1 como `In progress` e não declarar suporte iOS comprovado.
3. Aceitar que o critério “passkey em Android e iOS” da Fase 3 permaneça aberto até existir build iOS real ou aceite formal do bloqueio externo.
4. Executar a Fase 3 em iterações pequenas e verificáveis. A iteração 1 cobre governança, ADRs, modelo de dados de identidade, migração reversível e serviço de OTP com adaptador simulado e testes.
5. Não usar provedor real de SMS, não versionar segredos e não adicionar dependências de WebAuthn antes do ADR 0014.
6. Não misturar commits de fases diferentes; a branch da Fase 3 não altera os artefatos da Fase 1 além de documentação compartilhada.

## Consequências

- O backend avança em identidade sem esperar o ambiente Apple.
- A Fase 3 não pode ser marcada `Complete` enquanto o iOS não for exercitado ou o bloqueio for formalmente aceito.
- A branch da Fase 3 contém a história da Fase 1 até o commit `565f854`; ao integrar, a ordem será Fase 1 e depois Fase 3.
- O adaptador de SMS simulado permite desenvolver e testar sem custo, mas não prova entrega real de SMS.
- A decisão de biblioteca WebAuthn, formato de tokens e política de recuperação continua pendente e registrada em ADRs próprios.
