"""create the complete InterviewAI schema"""
from alembic import context, op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = None if context.is_offline_mode() else sa.inspect(bind)

    def missing_table(name: str) -> bool:
        return inspector is None or name not in inspector.get_table_names()

    def missing_index(table_name: str, index_name: str) -> bool:
        return inspector is None or index_name not in {index["name"] for index in inspector.get_indexes(table_name)}

    user_role = sa.Enum("USER", "ADMIN", name="userrole")
    interview_status = sa.Enum("CREATED", "IN_PROGRESS", "COMPLETED", "CANCELLED", name="interviewstatus")

    if missing_table("users"):
        op.create_table("users", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("full_name", sa.String(160), nullable=False), sa.Column("role", user_role, nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("email_verified", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)), sa.PrimaryKeyConstraint("id"))
    if missing_table("sessions"):
        op.create_table("sessions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True), nullable=False), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False), sa.Column("device_type", sa.String(40)), sa.Column("browser", sa.String(80)), sa.Column("operating_system", sa.String(80)), sa.Column("approximate_location", sa.String(120)), sa.Column("session_duration_seconds", sa.Integer()), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("resumes"):
        op.create_table("resumes", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("file_type", sa.String(100), nullable=False), sa.Column("file_size", sa.Integer(), nullable=False), sa.Column("storage_key", sa.String(500), nullable=False), sa.Column("extracted_text", sa.Text(), nullable=False), sa.Column("parsed_profile_json", sa.JSON(), nullable=False), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("deleted_at", sa.DateTime(timezone=True)), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("storage_key"))
    if missing_table("jobs"):
        op.create_table("jobs", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("title", sa.String(180), nullable=False), sa.Column("company_name", sa.String(180)), sa.Column("job_description", sa.Text(), nullable=False), sa.Column("parsed_analysis_json", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("interviews"):
        op.create_table("interviews", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("resume_id", sa.Uuid()), sa.Column("job_id", sa.Uuid()), sa.Column("interview_type", sa.String(50), nullable=False), sa.Column("difficulty", sa.String(30), nullable=False), sa.Column("duration_target_minutes", sa.Integer(), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("ended_at", sa.DateTime(timezone=True)), sa.Column("actual_duration_seconds", sa.Integer()), sa.Column("status", interview_status, nullable=False), sa.Column("overall_score", sa.Float()), sa.Column("final_feedback_json", sa.JSON()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("interview_questions"):
        op.create_table("interview_questions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("interview_id", sa.Uuid(), nullable=False), sa.Column("question_number", sa.Integer(), nullable=False), sa.Column("question_text", sa.Text(), nullable=False), sa.Column("category", sa.String(80), nullable=False), sa.Column("difficulty", sa.String(30), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("answers"):
        op.create_table("answers", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("question_id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("answer_text", sa.Text(), nullable=False), sa.Column("audio_storage_key", sa.String(500)), sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False), sa.Column("response_duration_seconds", sa.Integer()), sa.ForeignKeyConstraint(["question_id"], ["interview_questions.id"], ondelete="CASCADE"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("feedback"):
        op.create_table("feedback", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("answer_id", sa.Uuid(), nullable=False), sa.Column("technical_score", sa.Float(), nullable=False), sa.Column("communication_score", sa.Float(), nullable=False), sa.Column("relevance_score", sa.Float(), nullable=False), sa.Column("clarity_score", sa.Float(), nullable=False), sa.Column("confidence_score", sa.Float(), nullable=False), sa.Column("strengths", sa.JSON(), nullable=False), sa.Column("weaknesses", sa.JSON(), nullable=False), sa.Column("suggestions", sa.JSON(), nullable=False), sa.Column("ai_feedback", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["answer_id"], ["answers.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("answer_id"))
    if missing_table("ai_usage"):
        op.create_table("ai_usage", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("interview_id", sa.Uuid()), sa.Column("provider", sa.String(80), nullable=False), sa.Column("model", sa.String(120), nullable=False), sa.Column("request_type", sa.String(80), nullable=False), sa.Column("input_tokens", sa.Integer(), nullable=False), sa.Column("output_tokens", sa.Integer(), nullable=False), sa.Column("estimated_cost", sa.Float(), nullable=False), sa.Column("latency_ms", sa.Integer(), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("error_type", sa.String(80)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("credits"):
        op.create_table("credits", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("balance_minutes", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("user_id"))
    if missing_table("credit_transactions"):
        op.create_table("credit_transactions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("amount_minutes", sa.Integer(), nullable=False), sa.Column("transaction_type", sa.String(30), nullable=False), sa.Column("payment_reference", sa.String(180)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))
    if missing_table("analytics_events"):
        op.create_table("analytics_events", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid()), sa.Column("event_name", sa.String(80), nullable=False), sa.Column("event_timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("session_id", sa.Uuid()), sa.Column("interview_id", sa.Uuid()), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["interview_id"], ["interviews.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="SET NULL"), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"), sa.PrimaryKeyConstraint("id"))
    if missing_table("admin_audit_logs"):
        op.create_table("admin_audit_logs", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("admin_user_id", sa.Uuid(), nullable=False), sa.Column("action", sa.String(120), nullable=False), sa.Column("target_type", sa.String(80), nullable=False), sa.Column("target_id", sa.String(80)), sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False), sa.Column("ip_address", sa.String(64)), sa.Column("metadata_json", sa.JSON(), nullable=False), sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"))

    indexes = {
        "ix_users_email": ("users", "email"), "ix_sessions_user_id": ("sessions", "user_id"), "ix_resumes_user_id": ("resumes", "user_id"), "ix_jobs_user_id": ("jobs", "user_id"), "ix_interviews_user_id": ("interviews", "user_id"), "ix_interview_questions_interview_id": ("interview_questions", "interview_id"), "ix_answers_question_id": ("answers", "question_id"), "ix_answers_user_id": ("answers", "user_id"), "ix_ai_usage_user_id": ("ai_usage", "user_id"), "ix_credit_transactions_user_id": ("credit_transactions", "user_id"), "ix_analytics_events_user_id": ("analytics_events", "user_id"), "ix_analytics_events_event_name": ("analytics_events", "event_name"), "ix_admin_audit_logs_admin_user_id": ("admin_audit_logs", "admin_user_id")
    }
    for index_name, (table_name, column_name) in indexes.items():
        if missing_index(table_name, index_name):
            op.create_index(index_name, table_name, [column_name], unique=index_name == "ix_users_email")


def downgrade() -> None:
    for table_name in ("admin_audit_logs", "analytics_events", "credit_transactions", "credits", "ai_usage", "feedback", "answers", "interview_questions", "interviews", "jobs", "resumes", "sessions", "users"):
        op.drop_table(table_name)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS interviewstatus")
        op.execute("DROP TYPE IF EXISTS userrole")
