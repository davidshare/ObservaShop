"""Initial schema

Revision ID: b34563cd68c0
Revises:
Create Date: 2025-07-22 15:12:19.220111

"""

from typing import Sequence, Union

from alembic import op
import sqlmodel
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b34563cd68c0"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("description", sa.TEXT(), nullable=True),
        sa.Column("price", sa.NUMERIC(precision=10, scale=2), nullable=False),
        sa.Column("stock", sa.Integer(), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="product",
    )
    op.create_index(
        op.f("ix_product_products_id"),
        "products",
        ["id"],
        unique=False,
        schema="product",
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_product_products_id"), table_name="products", schema="product"
    )
    op.drop_table("products", schema="product")
    # ### end Alembic commands ###
