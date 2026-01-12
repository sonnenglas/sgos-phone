"""Add email_subject and email_message_id columns

Revision ID: 002
Revises: 001
Create Date: 2026-01-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add email_subject column for LLM-generated subject line
    op.add_column('calls', sa.Column('email_subject', sa.String(255)))

    # Add email_message_id column for Postmark delivery tracking
    op.add_column('calls', sa.Column('email_message_id', sa.String(100)))


def downgrade() -> None:
    op.drop_column('calls', 'email_message_id')
    op.drop_column('calls', 'email_subject')
