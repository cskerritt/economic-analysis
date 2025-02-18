"""change_age_fields_to_decimal

Revision ID: e83b3d01bdbd
Revises: d62011859c42
Create Date: 2025-02-14 13:44:36.298689

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e83b3d01bdbd'
down_revision = 'd62011859c42'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('medical_item', schema=None) as batch_op:
        batch_op.alter_column('age_initiated',
               existing_type=sa.INTEGER(),
               type_=sa.Numeric(precision=10, scale=2),
               existing_nullable=True)
        batch_op.alter_column('age_through',
               existing_type=sa.INTEGER(),
               type_=sa.Numeric(precision=10, scale=2),
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('medical_item', schema=None) as batch_op:
        batch_op.alter_column('age_through',
               existing_type=sa.Numeric(precision=10, scale=2),
               type_=sa.INTEGER(),
               existing_nullable=True)
        batch_op.alter_column('age_initiated',
               existing_type=sa.Numeric(precision=10, scale=2),
               type_=sa.INTEGER(),
               existing_nullable=True)

    # ### end Alembic commands ###
