"""align the user email uniqueness with the SQLAlchemy model"""
from alembic import context, op
import sqlalchemy as sa


revision = "0004_align_user_email_index"
down_revision = "0003_interview_final_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_users_email", table_name="users")
        op.drop_constraint("users_email_key", "users", type_="unique")
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        return

    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"]: index for index in inspector.get_indexes("users")}
    constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "ix_users_email" in indexes:
        if not indexes["ix_users_email"].get("unique"):
            op.drop_index("ix_users_email", table_name="users")
            op.create_index("ix_users_email", "users", ["email"], unique=True)
    elif "users_email_key" not in constraints:
        op.create_index("ix_users_email", "users", ["email"], unique=True)
    if "users_email_key" in constraints:
        op.drop_constraint("users_email_key", "users", type_="unique")


def downgrade() -> None:
    if context.is_offline_mode():
        op.drop_index("ix_users_email", table_name="users")
        op.create_unique_constraint("users_email_key", "users", ["email"])
        op.create_index("ix_users_email", "users", ["email"])
        return

    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"]: index for index in inspector.get_indexes("users")}
    constraints = {constraint["name"] for constraint in inspector.get_unique_constraints("users")}
    if "ix_users_email" in indexes:
        op.drop_index("ix_users_email", table_name="users")
    if "users_email_key" not in constraints:
        op.create_unique_constraint("users_email_key", "users", ["email"])
    op.create_index("ix_users_email", "users", ["email"])