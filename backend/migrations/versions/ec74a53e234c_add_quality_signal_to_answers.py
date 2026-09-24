"""add_quality_signal_to_answers

Revision ID: ec74a53e234c
Revises: reset_credits_to_one
"""
from alembic import op
import sqlalchemy as sa

revision = "ec74a53e234c"
down_revision = "reset_credits_to_one"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("answers")}

    if "quality_signal" not in existing_columns:
        with op.batch_alter_table("answers") as batch_op:
            batch_op.add_column(sa.Column("quality_signal", sa.String(length=30), nullable=True, server_default="normal"))
            batch_op.alter_column("quality_signal", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("answers")}

    if "quality_signal" in existing_columns:
        with op.batch_alter_table("answers") as batch_op:
            batch_op.drop_column("quality_signal")
