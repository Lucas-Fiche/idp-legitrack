"""Create usuarios schema and user table

Revision ID: a85df4b56616
Revises: e4d7ca7b70ef
Create Date: 2025-11-10 22:29:50.869811

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a85df4b56616'
down_revision = 'e4d7ca7b70ef'
branch_labels = None
depends_on = None

def upgrade():
    op.execute('CREATE SCHEMA IF NOT EXISTS usuarios')
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('username', sa.String(length=150), nullable=False, unique=True),
        sa.Column('email', sa.String(length=150), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=True),
        schema='usuarios'
    )

def downgrade():
    op.drop_table('users', schema='usuarios')
    op.execute('DROP SCHEMA IF EXISTS usuarios')
