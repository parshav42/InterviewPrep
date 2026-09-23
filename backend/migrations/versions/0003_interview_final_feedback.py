"""store validated final interview feedback"""
from alembic import context, op
import sqlalchemy as sa

revision = "0003_interview_final_feedback"
down_revision = "0002_ai_usage_and_job_analysis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        return
    inspector = sa.inspect(op.get_bind())
    if "final_feedback_json" not in {column["name"] for column in inspector.get_columns("interviews")}: 
        op.add_column("interviews", sa.Column("final_feedback_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    if context.is_offline_mode():
        return
    op.drop_column("interviews", "final_feedback_json")
