"""add interview media table

Revision ID: 2c0d4b97c9a5
Revises: c9715e5f8701
Create Date: 2026-09-25 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2c0d4b97c9a5"
down_revision = "c9715e5f8701"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "interview_media" in tables:
        return

    op.create_table(
        "interview_media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("interview_id", sa.Uuid(), nullable=True),
        sa.Column("media_type", sa.String(length=40), nullable=False, server_default="photo"),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_interview_media_user_id"), "interview_media", ["user_id"], unique=False)
    op.create_index(op.f("ix_interview_media_interview_id"), "interview_media", ["interview_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "interview_media" not in tables:
        return
    op.drop_index(op.f("ix_interview_media_interview_id"), table_name="interview_media")
    op.drop_index(op.f("ix_interview_media_user_id"), table_name="interview_media")
    op.drop_table("interview_media")
