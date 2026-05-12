"""Initial schema: orders, order_items, kitchen_tickets, payments
 
Revision ID: 001
Create Date: 2024-11-08
"""
from alembic import op
import sqlalchemy as sa
 
revision = "001"
down_revision = None
branch_labels = None
depends_on = None
 
 
def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("order_id",        sa.String(32),  primary_key=True),
        sa.Column("table_id",        sa.Integer(),   nullable=False),
        sa.Column("guests",          sa.Integer(),   nullable=False),
        sa.Column("status",          sa.String(20),  nullable=False, server_default="NEW"),
        sa.Column("comment",         sa.Text(),      nullable=True),
        sa.Column("version",         sa.Integer(),   nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(128), nullable=True, unique=True),
        sa.Column("created_at",      sa.DateTime(),  nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at",      sa.DateTime(),  nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_orders_table_id", "orders", ["table_id"])
    op.create_index("ix_orders_status",   "orders", ["status"])
 
    op.create_table(
        "order_items",
        sa.Column("item_id",   sa.String(36),  primary_key=True),
        sa.Column("order_id",  sa.String(32),  sa.ForeignKey("orders.order_id"), nullable=False),
        sa.Column("dish_id",   sa.String(32),  nullable=False),
        sa.Column("dish_name", sa.String(128), nullable=False),
        sa.Column("quantity",  sa.Integer(),   nullable=False),
        sa.Column("price",     sa.Float(),     nullable=False),
        sa.Column("station",   sa.String(16),  nullable=False),
        sa.Column("comment",   sa.Text(),      nullable=True),
    )
 
    op.create_table(
        "kitchen_tickets",
        sa.Column("ticket_id", sa.String(32), primary_key=True),
        sa.Column("order_id",  sa.String(32), sa.ForeignKey("orders.order_id"),
                  nullable=False, unique=True),
        sa.Column("status",    sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
    )
 
    op.create_table(
        "ticket_items",
        sa.Column("id",        sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("ticket_id", sa.String(32), sa.ForeignKey("kitchen_tickets.ticket_id"),
                  nullable=False),
        sa.Column("dish_id",   sa.String(32), nullable=False),
        sa.Column("dish_name", sa.String(128), nullable=False),
        sa.Column("quantity",  sa.Integer(),  nullable=False),
        sa.Column("station",   sa.String(16), nullable=False),
        sa.Column("is_done",   sa.Integer(),  nullable=False, server_default="0"),
    )
 
    op.create_table(
        "payments",
        sa.Column("payment_id",     sa.String(32), primary_key=True),
        sa.Column("order_id",       sa.String(32), sa.ForeignKey("orders.order_id"),
                  nullable=False, unique=True),
        sa.Column("amount",         sa.Float(),    nullable=False),
        sa.Column("currency",       sa.String(3),  nullable=False, server_default="RUB"),
        sa.Column("method",         sa.String(8),  nullable=False),
        sa.Column("status",         sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("retry_count",    sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("transaction_id", sa.String(64), nullable=True),
        sa.Column("created_at",     sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at",     sa.DateTime(), nullable=False,
                  server_default=sa.text("NOW()")),
    )
 
    op.create_table(
        "idempotent_requests",
        sa.Column("idempotency_key", sa.String(128), primary_key=True),
        sa.Column("order_id",        sa.String(32),  nullable=False),
        sa.Column("created_at",      sa.DateTime(),  nullable=False,
                  server_default=sa.text("NOW()")),
    )
 
 
def downgrade() -> None:
    op.drop_table("idempotent_requests")
    op.drop_table("payments")
    op.drop_table("ticket_items")
    op.drop_table("kitchen_tickets")
    op.drop_table("order_items")
    op.drop_table("orders")