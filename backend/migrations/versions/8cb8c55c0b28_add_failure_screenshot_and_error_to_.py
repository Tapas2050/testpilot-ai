"""add_failure_screenshot_and_error_to_test_results

Revision ID: 8cb8c55c0b28
Revises: ab3237ee3bf4
Create Date: 2026-10-13 13:27:23.762400

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8cb8c55c0b28'
down_revision: Union[str, None] = 'ab3237ee3bf4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('test_results', sa.Column('failure_screenshot_path', sa.String(length=512), nullable=True))
    op.add_column('test_results', sa.Column('screenshot_error', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('test_results', 'screenshot_error')
    op.drop_column('test_results', 'failure_screenshot_path')

