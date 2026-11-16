# ADR 0047 — Painel de moderação separado e identidade de operador

- **Status:** Aprovado e implementado em 2026-11-14.
- **Data:** 2026-11-14
- **Decisores:** responsável pelo produto e equipe técnica.
- **Relaciona:** ADR 0024 (retenção de resultados), ADR 0041 (Trust Factor), `docs/JOGA_DOCUMENTACAO_TECNICA.md` §12.4, Fases 17A/17B/17C.

## Contexto

A 17A/17B permitiam denunciar, priorizar e decidir, mas a operação dependia de
CLI e não havia identidade interna de moderador. O administrador não recebia
aviso persistido quando uma denúncia entrava na fila, e o painel de gestão não
era o lugar adequado para conteúdo sensível de moderação.

## Decisão

1. **Operadores explícitos.** A tabela `moderation_operators` identifica cada
   conta autorizada com papel `ADMIN` ou `MODERATOR`, estado ativo, autoria e
   data de desativação. O papel é verificado no servidor em cada requisição.
2. **Bootstrap por ambiente.** `JOGA_MODERATION_ADMIN_USER_IDS` promove contas a
   administrador sem seed manual. Operadores gravados no banco têm precedência;
   `JOGA_MODERATION_OPERATORS` permanece apenas como compatibilidade com a CLI.
3. **Painel separado.** A operação visual fica em `/moderation`, com cabeçalho
   “JOGA y MODERAÇÃO”, autenticação do painel web e nenhuma rota pública.
   A gestão de operadores é restrita a `ADMIN`.
4. **Notificação persistida.** Toda nova denúncia grava uma notificação
   `moderation_report` para cada operador ativo e para os admins de bootstrap.
   A fila do painel também atualiza periodicamente; push não é fonte de verdade.
5. **Decisão humana.** Medidas continuam limitadas a `DISMISS`, `WARN`,
   `RESTRICT_RANKED` e `SUSPEND_TEMP` (1–30 dias), com justificativa e auditoria.
   Recurso aceito revoga a medida. Suspensão permanente segue fora da fatia.
6. **Sem IA paga.** A triagem continua determinística (`rules_v1`); nenhum texto
   é enviado a terceiros. Classificador local/open-source depende de dataset e
   avaliação offline posteriores.

## Consequências

- Nova migração `b4c5d6e7f8a9` com `moderation_operators`.
- Dependências `get_moderator` e `require_admin` protegem as rotas internas.
- O painel web ganha `ModerationPage`, tipos, métodos de API e estilos próprios.
- A central de notificações do app continua sendo o histórico do jogador; o
  painel usa a fila como superfície operacional.
- A CLI `scripts/review_moderation.py` permanece como contingência.
- Auditoria registra criação/desativação de operador e decisões humanas.

## Alternativas descartadas

- **Reutilizar o painel de gestão:** misturaria conteúdo sensível de moderação
  com operação de organizações e ampliaria o escopo de acesso.
- **Autorizar por variável de ambiente apenas:** não permitiria revogar um
  operador sem reiniciar a API nem registrar quem concedeu o papel.
- **Notificar apenas por push:** push pode falhar e não é fonte de verdade.

## Pendências

- Classificador local/open-source com dataset rotulado e avaliação offline.
- Central de notificações dentro do painel web.
- Suspensão permanente com política, segundo revisor e revisão jurídica.
- Retenção definitiva/LGPD e direito de exclusão.
