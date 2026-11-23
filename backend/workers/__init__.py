"""Workers são processos separados, não microserviços.

Cada módulo aqui é um loop executável (``python -m workers.<nome>``) e não
contém regra de domínio: ele apenas drena a Outbox e chama o serviço do módulo.
"""
