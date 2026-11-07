# ADR 0029 — Sem fotos de pessoas: avatares gerados e mídia restrita a quadras

- **Status:** Aprovado pelo responsável em 2026-11-07.
- **Data:** 2026-11-07
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §20.4 e §21.5; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.6, §18 e §20.1; `PLANS.md` Fases 4 e 17.

## Contexto

O perfil do jogador e os espaços sociais — lobby, chat e clã — precisam de identidade visual. A alternativa usual, foto de perfil enviada pelo usuário, amplia a superfície de abuso: exposição de menores, doxxing, sextorsão, catfishing, impersonação, conteúdo sexual ou violento e uso de imagem de terceiros sem consentimento. Também exige moderação de imagem em escala, revisão humana, retenção e resposta a incidentes.

O protótipo mobile já usa avatares ilustrados. A decisão consolida essa direção e a estende ao produto.

## Decisão

1. O aplicativo não exibe fotos de pessoas.
2. A identidade visual do jogador é um avatar ilustrado gerado a partir de catálogo fechado de peças, cores e acessórios, no estilo boneco.
3. O usuário escolhe combinações válidas; não envia imagem, não desenha livremente e não insere texto no avatar.
4. O backend valida o avatar contra a versão vigente do catálogo e registra a escolha.
5. Fotos são permitidas apenas para quadras e estabelecimentos, em fluxo autenticado de organização, com revisão, allowlist de tipo, limite de tamanho, armazenamento privado e remoção de pessoas identificáveis.
6. A identidade visual de clã usa o mesmo catálogo fechado, sem upload de imagem.
7. Documentos de KYC continuam privados e nunca são exibidos no aplicativo.
8. Não há upload livre de imagem, áudio, vídeo ou arquivo em perfil, lobby ou chat no MVP.
9. Nome de exibição e `#tag` continuam sujeitos a validação e moderação de texto.
10. Denúncias de perfil continuam existindo; a moderação pode restringir nome, avatar ou conta.

## Alternativas consideradas

### A. Foto de perfil com moderação reativa

Maior identificação social, mas exige moderação de imagem em escala, tratamento de conteúdo ilegal, revisão humana e resposta a incidentes. Custo e risco incompatíveis com o MVP.

### B. Avatar gerado com catálogo fechado (adotado)

Reduz drasticamente a superfície de abuso, elimina upload e mantém identidade visual consistente. Limita a expressão individual, o que é aceitável no escopo inicial.

### C. Avatar com upload de imagem convertida em ilustração

Mantém customização, mas preserva o upload, o armazenamento de imagem pessoal e os riscos de conteúdo. Não adotado no MVP.

## Consequências

- Moderação de mídia de pessoas sai do escopo do MVP; permanecem a moderação de texto e a de fotos de quadra.
- O produto precisa definir e versionar o catálogo de peças, a tela de edição e a validação no backend.
- Perfis ficam menos identificáveis por aparência real; amizade e convites dependem de nome, `#tag` e contexto de partida.
- Fotos de quadra exigem fluxo próprio de revisão, armazenamento privado e política de remoção.
- Qualquer expansão para foto de pessoa ou upload livre exige nova ADR e revisão de privacidade, moderação e retenção.

## Critérios para revisão

- Necessidade comprovada de identificação visual real em contexto de segurança.
- Capacidade operacional de moderar imagem em escala.
- Base legal e política de retenção para imagens de pessoas.
