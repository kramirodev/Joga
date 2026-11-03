# ADR 0017 — Encerramento da Fase 3 com o bloqueio iOS aceito

- **Status:** Aprovado pelo responsável do produto em 2026-11-03, ao determinar a conclusão da Fase 3.
- **Data:** 2026-11-03
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `PLANS.md` (Fase 3), ADR 0012, ficha da Fase 3, `harness/build-log.md`.

## Contexto

A Fase 3 entregou backend de identidade e Android de ponta a ponta: OTP, cadastro/login, passkeys verificadas no servidor, sessões rotativas, troca de telefone, dispositivos, recuperação via passkey e hardening básico. O critério de aceite original exige passkey em **Android e iOS**.

O iOS continua bloqueado por ausência de conta Apple Developer, macOS/Xcode e `apple-app-site-association`; não há como executar build ou cerimônia iOS neste ambiente. O responsável determinou continuar e concluir a fase.

## Decisão

1. Declarar a Fase 3 **Complete** para backend e Android, com a evidência registrada.
2. Registrar formalmente que o critério iOS permanece **bloqueado**, não comprovado, e não declarar suporte iOS.
3. Manter a pendência iOS rastreável para uma fase futura ou decisão específica; a associação AASA e o build iOS continuam fora do que foi executado.
4. Não reduzir o escopo de segurança: as decisões de OTP, passkeys, sessões, telefone e recuperação permanecem como registradas nos ADRs 0013–0016.
5. O commit da Fase 3 inclui backend, app Android, testes, documentação e ADRs; nenhuma ação externa nova (deploy, custo, provedor real) é autorizada por esta decisão.

## Consequências

- A Fase 3 pode ser encerrada sem fingir suporte multiplataforma completo.
- iOS continua sendo risco de produto e deve ser retomado quando houver ambiente/conta autorizados.
- O Android foi validado com aparelho físico, passkey real do Credential Manager, OTP, sessão, troca de telefone e recuperação via passkey.
- A decisão de encerramento não ratifica os ADRs para produção; a ratificação final continua necessária antes de go-live.
