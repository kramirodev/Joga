# ADR 0022 — Remoção do marketplace de produtos do escopo inicial

- **Status:** Aprovado pelo responsável do produto em 2026-11-05.
- **Data:** 2026-11-05
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** `docs/JOGA_DOCUMENTACAO_CONCEITO_PRODUTO.md` §15, §16, §22 e §25; `GOALS.md`; `PLANS.md` Fases 11–19; `docs/JOGA_DOCUMENTACAO_TECNICA.md` §1, §2, §13–§18.

## Contexto

As versões 2.0 e parte da 3.0 do documento conceitual tratavam o marketplace de produtos como pilar do produto, com catálogo, variantes, estoque, pedidos, vendedores, retirada/entrega, código de recebimento, avaliações e disputas comerciais. A documentação técnica e o `PLANS.md` refletiam esse desenho nas Fases 11–18.

A revisão de escopo concluiu que o marketplace de produtos:

- não é necessário para validar o núcleo esportivo nem o fluxo de reservas;
- adiciona complexidade jurídica, operacional e de suporte desproporcional ao estágio atual;
- compete por atenção e capital com o fluxo de reservas, que é a fonte de receita inicial;
- exige um PSP e um modelo de disputas diferentes do fluxo de quadras.

O marketplace já havia sido adiado na versão 3.0, mas continuava descrito em detalhe e ainda organizava fases inteiras do roadmap.

## Decisão

1. O marketplace de produtos **não faz parte do escopo inicial** e deixa de ser um pilar do produto.
2. Catálogo, variantes, estoque, pedidos, vendedores, retirada/entrega, código de recebimento, avaliações comerciais e disputas de produtos **não serão especificados nem implementados** nesta etapa.
3. O nome **JOGA y LOJA** deixa de ser usado na documentação ativa. Se o marketplace for reavaliado, o nome poderá ser retomado em uma decisão própria.
4. Lojas esportivas podem participar apenas como patrocinadoras ou anunciantes, sem vender produtos dentro do aplicativo.
5. A retirada do marketplace **não** retira a atividade comercial de reservas de quadras, parcerias, patrocínios e publicidade contextual.
6. Qualquer reintrodução exige nova decisão de produto, nova especificação técnica, revisão jurídica, definição de PSP e avaliação de capacidade operacional. Não reativar por código antigo, documento antigo ou fase antiga.
7. As fases comerciais do `PLANS.md` passam a ser organizadas em torno de: organizações e painel, quadras e agenda, reservas e temporizadores, pagamentos e reembolsos, interface financeira do estabelecimento, clubes, moderação, publicidade e lançamento.

## Consequências

- `GOALS.md` passa a ter três pilares: competitividade, comunidade e infraestrutura esportiva/reservas, com confiança como camada transversal.
- A documentação técnica deixa de modelar `stores`, `products`, `product_variants`, `inventory_*`, `orders`, `order_items`, `fulfillments`, `receipt_codes`, `returns` e `commerce_disputes`.
- O painel de gestão deixa de ser “painel de lojas” e passa a ser painel de estabelecimentos esportivos.
- O roadmap ganha espaço para KYC do recebedor, interface financeira do recebedor e conciliação, que antes não existiam.
- Nenhuma migração, tabela ou endpoint de marketplace deve ser criado com base em documentos anteriores.
- A decisão não impede uma expansão futura, mas ela não está prometida nem pré-especificada.

## Alternativas consideradas

1. **Manter o marketplace apenas documentado como expansão futura.** Rejeitada porque o detalhamento continuava orientando fases, modelos de dados e esforço de leitura sem compromisso de execução.
2. **Manter um catálogo mínimo sem pagamento.** Rejeitada porque não resolve o problema principal e cria obrigações de anúncio, moderação e suporte.
3. **Substituir o marketplace por um classificados de equipamentos usados.** Rejeitada por risco de fraude e por desvio do foco em reservas.
