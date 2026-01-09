"""Initial migration - create voicemails table

Revision ID: 001
Revises:
Create Date: 2026-01-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "voicemails",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("from_number", sa.String(50), nullable=True),
        sa.Column("to_number", sa.String(50), nullable=True),
        sa.Column("to_number_name", sa.String(255), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("local_file_path", sa.String(500), nullable=True),
        sa.Column("unread", sa.Boolean(), default=True),
        # Transcription fields
        sa.Column("transcription_status", sa.String(20), default="pending"),
        sa.Column("transcription_text", sa.Text(), nullable=True),
        sa.Column("transcription_language", sa.String(10), nullable=True),
        sa.Column("transcription_confidence", sa.Float(), nullable=True),
        sa.Column("transcribed_at", sa.DateTime(timezone=True), nullable=True),
        # Summary fields (future)
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("summary_model", sa.String(100), nullable=True),
        sa.Column("summarized_at", sa.DateTime(timezone=True), nullable=True),
        # Metadata
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_voicemails_received_at", "voicemails", ["received_at"], unique=False)
    op.create_index("idx_voicemails_status", "voicemails", ["transcription_status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_voicemails_status", table_name="voicemails")
    op.drop_index("idx_voicemails_received_at", table_name="voicemails")
    op.drop_table("voicemails")
