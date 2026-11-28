"""merge do catálogo de assinatura e da observabilidade

Revision ID: bc23de45fa67
Revises: ab12cd34ef56, f1a2b3c4d5e6
Create Date: 2026-11-27 00:00:00.000000

Os dois ramos já estavam no repositório sem merge e deixavam ``upgrade head``
ambíguo. Este merge não altera schema; apenas reconecta a árvore.
"""

from collections.abc import Sequence

revision: str = "bc23de45fa67"
down_revision: str | Sequence[str] | None = ("ab12cd34ef56", "f1a2b3c4d5e6")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
