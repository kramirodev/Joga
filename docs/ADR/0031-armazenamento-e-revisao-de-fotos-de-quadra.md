# ADR 0031 — Armazenamento e revisão de fotos de quadra na Fase 12A

- **Status:** Aprovado para a 12A em 2026-11-07; storage de produção e revisão independente pendentes.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §20.4; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.6, §18, §19 e §20.1; `docs/ADR/0029-sem-fotos-de-pessoas-e-avatares-gerados.md`; `PLANS.md` Fase 12.

## Contexto

A ADR 0029 permitiu fotos apenas de quadras/estabelecimentos, com revisão, armazenamento privado e remoção de pessoas identificáveis. A Fase 12A precisa implementar upload e serving sem introduzir storage público, URL arbitrária ou revisão inexistente. Também é preciso decidir quem revisa na ausência de uma ferramenta de moderação, que pertence à Fase 17.

## Decisão

1. O desenvolvimento usa armazenamento local privado, fora de qualquer diretório estático, com chave aleatória e acesso somente por endpoint autenticado.
2. O arquivo é validado pelo conteúdo real, reencodado em JPEG e tem EXIF/metadados removidos. A API não confia em nome, extensão ou `Content-Type` do cliente.
3. Limites de bytes, pixels e dimensões são configuráveis; imagens fora da allowlist (JPEG, PNG, WebP) são rejeitadas.
4. Toda foto nasce `PENDING`. Os estados são `PENDING`, `APPROVED`, `REJECTED` e `REMOVED`.
5. Na 12A, a revisão inicial é feita por `OWNER` ou `ADMIN` da organização, com motivo obrigatório na rejeição e auditoria. `OPERATOR` pode enviar e remover, mas não revisar.
6. A revisão independente, a denúncia de foto e a moderação de abuso entram na Fase 17. Até lá, a foto aprovada não deve ser tratada como curadoria independente.
7. Produção exige storage de objetos, criptografia, backup, retenção, serving autorizado e limpeza de órfãos; a decisão de provedor fica pendente.
8. A remoção apaga o arquivo e mantém o registro auditável do evento.
9. Fotos de pessoas continuam proibidas; a revisão deve rejeitar pessoa identificável em primeiro plano.

## Alternativas consideradas

### A. Autoaprovação no upload

Simples, mas elimina a revisão e publica conteúdo sem controle. Rejeitada.

### B. Revisor de plataforma desde a 12A

Mais íntegro, mas exige ferramenta interna e operação que pertencem à Fase 17. Adiada.

### C. Revisão pelo `OWNER`/`ADMIN` com auditoria (adotada)

Permite fechar o fluxo da 12A sem criar uma ferramenta de moderação prematura. O risco de autoaprovação é residual e explicitado.

### D. Storage de objetos desde já

Produção exige provedor, contrato e custo. O adaptador local mantém o domínio desacoplado, mas não serve para produção.

## Consequências

- O fluxo de fotos funciona no painel local sem URL pública e sem acesso cruzado entre organizações.
- A revisão é provisória e precisa ser substituída ou complementada por revisão independente antes da descoberta pública no app.
- O storage local não é adequado para múltiplas instâncias, backup ou produção.
- A remoção de metadados reduz exposição de localização, mas não substitui a revisão humana.
- O serving autorizado e o `Cache-Control: no-store` evitam cache público.

## Critérios para revisão

- Definição do provedor de storage e da política de retenção.
- Implantação da revisão independente e do canal de denúncia de foto.
- Evidência de abuso ou volume que exija fila de revisão dedicada.
- Revisão jurídica de retenção e tratamento de imagem de estabelecimento.
