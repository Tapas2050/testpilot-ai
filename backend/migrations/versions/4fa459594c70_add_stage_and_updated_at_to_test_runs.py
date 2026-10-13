"""add_stage_and_updated_at_to_test_runs

Revision ID: 4fa459594c70
Revises: 8cb8c55c0b28
Create Date: 2026-10-13 16:28:42.391169

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4fa459594c70'
down_revision: Union[str, None] = '8cb8c55c0b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_runs', sa.Column('stage', sa.String(length=32), server_default='QUEUED', nullable=False))
    op.add_column('test_runs', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    op.drop_column('test_runs', 'updated_at')
    op.drop_column('test_runs', 'stage')
