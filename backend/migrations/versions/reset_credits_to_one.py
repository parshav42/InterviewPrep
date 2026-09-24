"""reset credit balances to one free interview"""
from alembic import op
import sqlalchemy as sa

revision = "reset_credits_to_one"
down_revision = "f93e91889d04"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("credits")}

    if "balance_minutes" in columns:
        op.execute("UPDATE credits SET balance_minutes = 1")
    elif "balance_interviews" in columns:
        op.execute("UPDATE credits SET balance_interviews = 1")


def downgrade():
    pass
