# ADR 0029 — Sem fotos de pessoas: identidade por ícones e mídia restrita a quadras

- **Status:** Aprovado pelo responsável em 2026-11-07. **Revisão 2** aprovada em 2026-11-19: substitui o avatar ilustrado por identidade de ícones de catálogo fechado e mantém a proibição de fotos de pessoas.
- **Data:** 2026-11-07
- **Revisão 2:** 2026-11-19
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §20.4 e §21.5; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.6, §18 e §20.1; `docs/ASSETS_SVG_INVENTARIO.md`; `PLANS.md` Fases 4 e 17.

## Contexto

O perfil do jogador e os espaços sociais — lobby, chat e clã — precisam de identidade visual. A alternativa usual, foto de perfil enviada pelo usuário, amplia a superfície de abuso: exposição de menores, doxxing, sextorsão, catfishing, impersonação, conteúdo sexual ou violento e uso de imagem de terceiros sem consentimento. Também exige moderação de imagem em escala, revisão humana, retenção e resposta a incidentes.

O protótipo mobile usava avatares ilustrados. A revisão 2 substitui esse modelo por ícones de perfil de catálogo fechado, sem corpo, camadas ou upload.

## Decisão

1. O aplicativo não exibe fotos de pessoas.
2. A identidade visual do jogador é um **ícone de perfil** de catálogo fechado, combinado com **moldura**, **cor de destaque**, **ícone de entrada**, **emote** e **badge**. Não há corpo, camadas, tom de pele, cabelo, roupa ou expressão.
3. O usuário escolhe itens válidos do catálogo; não envia imagem, não desenha livremente e não insere texto no ícone.
4. O backend valida os códigos e a versão vigente do catálogo e registra a escolha, com um item equipado por slot.
5. Fotos são permitidas apenas para quadras e estabelecimentos, em fluxo autenticado de organização, com revisão, allowlist de tipo, limite de tamanho, armazenamento privado e remoção de pessoas identificáveis.
6. A identidade visual de clã usa o mesmo catálogo fechado de ícones e símbolos, sem upload de imagem.
7. Documentos de KYC continuam privados e nunca são exibidos no aplicativo.
8. Não há upload livre de imagem, áudio, vídeo ou arquivo em perfil, lobby ou chat no MVP.
9. Nome de exibição e `#tag` continuam sujeitos a validação e moderação de texto.
10. Denúncias de perfil continuam existindo; a moderação pode restringir nome, ícone de perfil ou conta e redefinir o ícone padrão.

## Revisão 2 — 2026-11-19

A revisão 2 troca o character creator por identidade por ícones e não cria ADR nova. Ela mantém integralmente a decisão de não exibir fotos de pessoas e a restrição de mídia a quadras e estabelecimentos. O catálogo de identidade é fechado e versionado; a moderação pode redefinir o ícone padrão em caso de abuso.

Itens alterados nesta revisão:

- título e item 2: “avatar ilustrado gerado” e “catálogo de peças” passam a ícone de perfil + moldura + cor de destaque + ícone de entrada + emote + badge;
- item 3: a escolha de combinações passa a escolha de códigos válidos do catálogo;
- item 4: a validação de avatar passa a validação dos códigos e da versão do catálogo;
- item 10: a moderação pode redefinir o ícone padrão.

## Alternativas consideradas

### A. Foto de perfil com moderação reativa

Maior identificação social, mas exige moderação de imagem em escala, tratamento de conteúdo ilegal, revisão humana e resposta a incidentes. Custo e risco incompatíveis com o MVP.

### B. Identidade por ícones de catálogo fechado (adotado)

Reduz drasticamente a superfície de abuso, elimina upload e mantém identidade visual consistente. Limita a expressão individual, o que é aceitável no escopo inicial.

### C. Avatar com upload de imagem convertida em ilustração

Mantém customização, mas preserva o upload, o armazenamento de imagem pessoal e os riscos de conteúdo. Não adotado no MVP.

## Consequências

- Moderação de mídia de pessoas sai do escopo do MVP; permanecem a moderação de texto e a de fotos de quadra.
- O produto precisa definir e versionar o catálogo de ícones de perfil, molduras, cores de destaque, ícones de entrada, emotes e badges, a tela de edição e a validação no backend.
- Perfis ficam menos identificáveis por aparência real; amizade e convites dependem de nome, `#tag` e contexto de partida.
- Fotos de quadra exigem fluxo próprio de revisão, armazenamento privado e política de remoção.
- Qualquer expansão para foto de pessoa ou upload livre exige nova ADR e revisão de privacidade, moderação e retenção.

## Critérios para revisão

- Necessidade comprovada de identificação visual real em contexto de segurança.
- Capacidade operacional de moderar imagem em escala.
- Base legal e política de retenção para imagens de pessoas.
