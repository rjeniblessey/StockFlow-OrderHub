from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------

class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: Literal["admin", "customer"]

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------- Product ----------

class CreateProductRequest(BaseModel):
    name: str
    description: str | None = None
    price: float = Field(gt=0)
    quantity: int = Field(ge=0)


class CreateProductResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    price: float
    quantity: int
    seller_username: str

    class Config:
        from_attributes = True


# ---------- Order ----------

class CreateOrderRequest(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class CreateOrderResponse(BaseModel):
    id: int
    product_id: int | None
    product_name: str
    quantity: int
    total_price: float
    status: Literal["placed", "shipped", "delivered"]
    created_at: datetime
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    customer_username: str

    class Config:
        from_attributes = True
