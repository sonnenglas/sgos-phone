"""Initial schema for Phone app

Revision ID: 001
Revises: None
Create Date: 2025-01-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Settings table
    op.create_table(
        'settings',
        sa.Column('key', sa.String(100), primary_key=True),
        sa.Column('value', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Insert default settings
    op.execute("""
        INSERT INTO settings (key, value) VALUES
        ('sync_interval_minutes', '15'),
        ('auto_transcribe', 'true'),
        ('auto_summarize', 'true'),
        ('auto_email', 'false'),
        ('helpdesk_api_url', ''),
        ('last_sync_at', '')
    """)

    # Voicemails table
    op.create_table(
        'voicemails',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='placetel'),

        # Call info
        sa.Column('from_number', sa.String(50)),
        sa.Column('to_number', sa.String(50)),
        sa.Column('to_number_name', sa.String(255)),
        sa.Column('duration', sa.Integer()),
        sa.Column('received_at', sa.DateTime(timezone=True)),
        sa.Column('unread', sa.Boolean(), server_default='true'),

        # Audio
        sa.Column('file_url', sa.Text()),
        sa.Column('local_file_path', sa.String(500)),

        # Transcription
        sa.Column('transcription_status', sa.String(20), server_default='pending'),
        sa.Column('transcription_text', sa.Text()),
        sa.Column('transcription_language', sa.String(10)),
        sa.Column('transcription_confidence', sa.Float()),
        sa.Column('transcribed_at', sa.DateTime(timezone=True)),

        # Summary
        sa.Column('corrected_text', sa.Text()),
        sa.Column('summary', sa.Text()),
        sa.Column('summary_model', sa.String(100)),
        sa.Column('summarized_at', sa.DateTime(timezone=True)),

        # AI Classification
        sa.Column('sentiment', sa.String(20)),  # positive, negative, neutral
        sa.Column('emotion', sa.String(20)),  # angry, frustrated, happy, confused, calm, urgent
        sa.Column('category', sa.String(30)),  # sales_inquiry, existing_order, new_inquiry, complaint, general
        sa.Column('is_urgent', sa.Boolean(), server_default='false'),

        # Email/Helpdesk
        sa.Column('email_status', sa.String(20), server_default='pending'),
        sa.Column('email_sent_at', sa.DateTime(timezone=True)),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),

        sa.UniqueConstraint('provider', 'external_id', name='uq_provider_external_id'),
    )

    # Indexes
    op.create_index('idx_voicemails_received_at', 'voicemails', ['received_at'])
    op.create_index('idx_voicemails_status', 'voicemails', ['transcription_status'])
    op.create_index('idx_voicemails_email_status', 'voicemails', ['email_status'])


def downgrade() -> None:
    op.drop_table('voicemails')
    op.drop_table('settings')
