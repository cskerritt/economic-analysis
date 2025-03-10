"""Add category column to medical_item table

Revision ID: 8f3dcaac6232
Revises: 98a5d78a0d9b
Create Date: 2025-02-24 11:40:23.102546

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f3dcaac6232'
down_revision = '98a5d78a0d9b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('medical_item', schema=None) as batch_op:
        batch_op.add_column(sa.Column('category', sa.String(length=100), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('medical_item', schema=None) as batch_op:
        batch_op.drop_column('category')

    # ### end Alembic commands ###
