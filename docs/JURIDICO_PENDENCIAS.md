# Pendências jurídicas, fiscais e regulatórias

Atualizado em 2026-11-15. Este arquivo concentra o que depende de advogado,
contador, financeiro ou decisão de produto com efeito legal. Não é parecer
jurídico; é a lista de perguntas e decisões que precisam de validação
profissional antes de escalar o JOGA.

## Contexto atual

- O beta real começa com **conta CPF** no Mercado Pago, por cerca de um mês.
- MEI/PJ fica para depois por custo; a migração precisa acontecer antes de
  volume relevante, publicidade paga ou operação comercial contínua.
- Checkout Transparente está em ambiente de teste (30% do onboarding).
- O dinheiro das reservas/pacotes fica centralizado na conta do JOGA; o repasse
  à quadra é manual/registrado no ledger (ADR 0040/0048).
- Não há split, recebedor automático, custódia regulada nem promessa de
  repasse automático.

## 1. Bloqueios de maior risco (resolver antes de escalar)

| Item | Por que importa | Próximo passo |
|---|---|---|
| Operar dinheiro de terceiros em conta CPF | Mistura patrimônio pessoal, receita, tributos e responsabilidade civil | Definir data-limite do beta com CPF; abrir MEI/PJ antes de aumentar volume |
| Contrato com a quadra (fornecedor) | Define repasse, cancelamento, no-show, responsabilidade e nota fiscal | Minuta de contrato de intermediação/fornecimento com teto e obrigações |
| Termos de uso e política de privacidade | Consentimento, cancelamento, reembolso, dados e foro | Revisão jurídica antes do beta |
| Política de reembolso | CDC, direito de arrependimento e consumo de crédito | Validar a proposta da seção 3 |
| Nota fiscal e tributação do ingresso | ISS, base de comissão, retenção, IBS/CBS | Contador e advogado tributário |
| Custódia e insolvência | O que acontece com saldo de terceiros se a conta for bloqueada | Parecer sobre segregação/conta específica e limites do modelo |
| MED/chargeback | Quem absorve, como bloquear repasse e como cobrar | Política escrita e regra no ledger |
| KYC das quadras | Contraparte, titularidade da chave Pix e prevenção a fraude | Processo de cadastro, documentos e verificação |

## 2. Fiscal e contábil

- Base de cálculo da comissão do JOGA e do valor repassado à quadra.
- Emissão de nota fiscal: quem emite, para quem, com qual município/ISS.
- Retenção de tributos pelo tomador e obrigações acessórias.
- Tratamento de ingressos gratuitos, descontos, créditos e reembolsos.
- IBS/CBS e período de transição.
- Conciliação entre receita no Mercado Pago, ledger interno e extrato bancário.
- Política de tarifas: quem paga a taxa do Pix, do payout e do reembolso.
- Reserva para MED/chargeback e provisão de reembolsos.

## 3. Reembolso e direito do consumidor

Proposta atual para discussão (não aprovada):

- **Crédito comprado:** não expira. Nos 7 dias do CDC, devolução em dinheiro pelo mesmo meio; depois, devolução em crédito enquanto a conta estiver ativa e em dinheiro no encerramento, conforme ADR 0049 C8/C13.
- **Passe:** assinatura de franquia mensal; a franquia não acumula e não se converte em saldo. Política de reembolso após a primeira entrega ainda não aprovada.
- **No-show, cut-off e desistência:** regra pendente na ADR 0039; não tratar como confisco automático.
- **Tickets gratuitos/promocionais:** não geram reembolso em dinheiro; expiram com a temporada.
- **Crédito comprado expirado:** não existe; a expiração de crédito comprado é proibida pela ADR 0049.

Perguntas para o jurídico:

1. O direito de arrependimento de 7 dias do CDC se aplica a créditos digitais
   já parcialmente consumidos? Como documentar?
2. Reembolso proporcional ao saldo é aceitável ou o consumidor pode exigir o
   valor integral dentro dos 7 dias, mesmo tendo usado parte?
3. Passe trimestral com entrega mensal: pode ser tratado como assinatura sem
   reembolso após a primeira entrega? Precisa de carência?
4. No-show e cut-off podem gerar perda total do valor? Como redigir a cláusula
   para reduzir risco de nulidade?
5. Quem absorve a tarifa do PSP no reembolso: JOGA ou consumidor?
6. Reembolso deve voltar pelo mesmo meio de pagamento? Pix de terceiro é
   permitido?
7. Como tratar pack comprado com mistura de ingressos pagos e gratuitos?
8. Prazo máximo para concluir o reembolso e dever de informar o status.
9. Obrigação de comprovante/recibo do reembolso.
10. Se a quadra já recebeu o repasse, quem suporta o estorno?

Recomendação técnica: usar **reembolso do PSP sobre o pagamento original**
(volta para o pagador), não um Pix manual novo. Pix manual só como contingência,
com titularidade confirmada e comprovante.

## 4. Contratos e relações comerciais

- Contrato JOGA ↔ quadra: objeto, preço, repasse, prazo, cancelamento,
  no-show, responsabilidade, nota fiscal, rescisão e foro.
- Contrato JOGA ↔ jogador: termos de uso, regras de comunidade, moderação,
  suspensão, reembolso e privacidade.
- Contrato JOGA ↔ Mercado Pago: termos da conta, uso comercial, payout e
  responsabilidade por chargeback.
- Eventual contrato com clã/organizador e publicidade (Fase 18).
- Propriedade intelectual: marca, avatar, catálogo cosmético e conteúdo de clã.
- Seguro/garantia para eventos e responsabilidade civil, se necessário.

## 5. LGPD e dados

- Base legal para telefone, e-mail, localização, presença, CPF e histórico.
- Retenção definitiva de mensagens, contexto de moderação, resultados e
  evidências. O ADR 0024 fixa política provisória; o ADR 0027 usa 730 dias para
  mensagens. Reconciliar antes da LGPD.
- CPF: base legal, cifra, acesso restrito e prazo (ADR 0049 §3.8/§9.3).
- NFS-e: guarda do documento, município e compartilhamento com o tomador.
- Direito de exclusão versus obrigação de guardar dados financeiros/fiscais.
- Check-in por localização: minimização, finalidade e prazo.
- Compartilhamento com PSP, SMS, push, storage e escrow.
- Política de incidentes e comunicação de vazamento.
- Registro de operações de tratamento e encarregado (DPO).
- Consentimento de menores e idade mínima.

## 6. Consumo, comunidade e moderação

- Regras de suspensão temporária e permanente, contraditório e recurso.
- Consequência de denúncia falsa e limites.
- Conteúdo de chat, assédio, ameaça e ódio: dever de moderação e prazos.
- Publicidade e patrocínio: identificação, filtros e efeito competitivo.
- Sorteios, torneios e premiações: regras e autorizações, se houver.
- Política de violência, apostas e conduta em eventos presenciais.

## 7. Financeiro e antifraude

- Política de MED/chargeback: prazo, evidências, bloqueio de repasse e cobrança.
- Limite de valor por conta, por dia e por beta.
- Triple-check de titularidade da chave Pix da quadra.
- Aprovação dupla para repasses acima de limite.
- Conciliação periódica obrigatória e tratamento de divergência.
- Registro de comprovantes e retenção fiscal.
- Procedimento para conta bloqueada pelo PSP.

## 8. Decisões já registradas

- Modelo tributário: intermediação por mandato, base de cálculo na comissão,
  saldo em reais, preço em duas linhas (espaço + taxa) (ADR 0049). Bloqueado por
  parecer fiscal e jurídico.
- Mercado Pago é o PSP do protótipo com jogadores reais (ADR 0048).
- Sem split/recebedor; repasse centralizado e manual/ledger.
- Inter/Pagar.me ficam para o futuro.
- Suspensão permanente ainda depende de política e revisão jurídica.
- Publicidade (Fase 18) só depois de ADR e revisão.

## 9. Itens que não são de backend

Estes itens não devem ser tratados como tarefa de código: parecer fiscal,
parecer jurídico de intermediação/custódia/CDC, KYC contratual, termos de uso,
retenção definitiva/LGPD, direito de exclusão e revisão de suspensão
permanente. O backend implementa a regra depois que ela for aprovada.
