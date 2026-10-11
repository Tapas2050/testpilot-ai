"""add_checks_to_test_cases

Revision ID: ab3237ee3bf4
Revises: fb153e7a31a1
Create Date: 2026-10-12 04:04:38.557192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab3237ee3bf4'
down_revision: Union[str, None] = 'fb153e7a31a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    op.add_column('test_cases', sa.Column('checks', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    op.drop_column('test_cases', 'checks')
