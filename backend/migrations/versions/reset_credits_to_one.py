"""reset credit balances to one free interview"""
from alembic import op

revision = "reset_credits_to_one"
down_revision = "f93e91889d04"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("UPDATE credits SET balance_minutes = 1")


def downgrade():
    pass
