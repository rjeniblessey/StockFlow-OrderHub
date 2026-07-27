from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # "admin" or "customer"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )
    orders = relationship(
        "Order", back_populates="customer", foreign_keys="Order.customer_id"
    )
    # Only populated for admin/seller accounts — the products they've listed.
    products = relationship("Product", back_populates="seller")


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")


class Product(Base):
    __tablename__ = "product"
    __table_args__ = (
        # A name only has to be unique within one seller's own catalog —
        # two different sellers can both list a "Blue T-Shirt".
        UniqueConstraint("seller_id", "name", name="uq_seller_product_name"),
    )

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    name = Column(String(60), nullable=False)
    description = Column(String(255), nullable=True)
    price = Column(Float, nullable=False)
    quantity = Column(Integer, nullable=False)

    seller = relationship("User", back_populates="products")
    orders = relationship("Order", back_populates="product")

    @property
    def seller_username(self) -> str | None:
        return self.seller.username if self.seller else None


class Order(Base):
    __tablename__ = "order"

    id = Column(Integer, primary_key=True, index=True)
    # nullable on purpose: if the product is later removed from the shelf,
    # this FK is set to NULL instead of blocking the delete or the order row.
    product_id = Column(Integer, ForeignKey("product.id", ondelete="SET NULL"), nullable=True)
    # snapshot taken at order time, so history still reads fine even after
    # the product itself has been deleted.
    product_name = Column(String(60), nullable=False)
    customer_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    # Snapshot of which seller this order belongs to — kept even if the
    # product itself is later deleted, so a seller's order list stays
    # correctly scoped to just their own sales.
    seller_id = Column(Integer, ForeignKey("user.id", ondelete="SET NULL"), nullable=True, index=True)
    quantity = Column(Integer, nullable=False)
    total_price = Column(Float, nullable=False)
    # "placed" -> "shipped" (seller sends it) -> "delivered" (buyer confirms)
    status = Column(String(20), default="placed", nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    shipped_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    product = relationship("Product", back_populates="orders")
    customer = relationship("User", back_populates="orders", foreign_keys=[customer_id])
    seller = relationship("User", foreign_keys=[seller_id])
