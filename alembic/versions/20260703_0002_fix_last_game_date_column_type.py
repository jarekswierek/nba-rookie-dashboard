"""Fix last_game_date column type from TIMESTAMP to DATE.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "player_game_logs",
        "last_game_date",
        type_=sa.Date(),
        existing_type=sa.DateTime(timezone=False),
        existing_nullable=True,
        postgresql_using="last_game_date::date",
    )


def downgrade() -> None:
    op.alter_column(
        "player_game_logs",
        "last_game_date",
        type_=sa.DateTime(timezone=False),
        existing_type=sa.Date(),
        existing_nullable=True,
    )
