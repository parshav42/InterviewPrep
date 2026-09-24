"""add probe tracking and skip flag

Revision ID: c9715e5f8701
Revises: ec74a53e234c
Create Date: 2026-09-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "c9715e5f8701"
down_revision = "ec74a53e234c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_questions") as batch_op:
        batch_op.add_column(sa.Column("probe_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.alter_column("probe_count", server_default=None)

    with op.batch_alter_table("answers") as batch_op:
        batch_op.add_column(sa.Column("skipped", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.alter_column("skipped", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("answers") as batch_op:
        batch_op.drop_column("skipped")

    with op.batch_alter_table("interview_questions") as batch_op:
        batch_op.drop_column("probe_count")
