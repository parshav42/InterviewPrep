"""add structured job analysis and remote LLM usage fields"""
from alembic import context, op
import sqlalchemy as sa

revision = "0002_ai_usage_and_job_analysis"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    if "parsed_analysis_json" not in {column["name"] for column in inspector.get_columns("jobs")}: 
        op.add_column("jobs", sa.Column("parsed_analysis_json", sa.JSON(), nullable=True))
    usage_columns = {column["name"] for column in inspector.get_columns("ai_usage")}
    if "latency_ms" not in usage_columns:
        op.add_column("ai_usage", sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"))
    if "status" not in usage_columns:
        op.add_column("ai_usage", sa.Column("status", sa.String(length=30), nullable=False, server_default="success"))
    if "error_type" not in usage_columns:
        op.add_column("ai_usage", sa.Column("error_type", sa.String(length=80), nullable=True))


def downgrade() -> None:
    if context.is_offline_mode():
        return
    op.drop_column("ai_usage", "error_type")
    op.drop_column("ai_usage", "status")
    op.drop_column("ai_usage", "latency_ms")
    op.drop_column("jobs", "parsed_analysis_json")
