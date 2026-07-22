from datetime import timedelta, datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import model
import schema
from database import engine, get_db

model.Base.metadata.create_all(bind=engine)  # create tables

app = FastAPI(title="E-Commerce API")

# Allow the static frontend (and any dev server) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = FastAPI(title="E-Commerce API - v1")


# ============================================================
# AUTH — admin and customer are fully separate account pools
# ============================================================

@api.post("/signup/admin", response_model=schema.UserResponse, status_code=status.HTTP_201_CREATED)
def signup_admin(payload: schema.SignupRequest, db: Session = Depends(get_db)):
    user = auth.create_user(db, payload.username, payload.email, payload.password, role="admin")
    return user


@api.post("/signup/customer", response_model=schema.UserResponse, status_code=status.HTTP_201_CREATED)
def signup_customer(payload: schema.SignupRequest, db: Session = Depends(get_db)):
    user = auth.create_user(db, payload.username, payload.email, payload.password, role="customer")
    return user


def _login(payload: schema.LoginRequest, role: str, db: Session) -> schema.TokenResponse:
    user = auth.authenticate_user(db, payload.username, payload.password, role=role)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = auth.create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = auth.create_refresh_token(db, user.id)
    return schema.TokenResponse(access_token=access_token, refresh_token=refresh_token, user=user)


@api.post("/login/admin", response_model=schema.TokenResponse)
def login_admin(payload: schema.LoginRequest, db: Session = Depends(get_db)):
    return _login(payload, role="admin", db=db)


@api.post("/login/customer", response_model=schema.TokenResponse)
def login_customer(payload: schema.LoginRequest, db: Session = Depends(get_db)):
    return _login(payload, role="customer", db=db)


@api.post("/refresh", response_model=schema.TokenResponse)
def refresh_token(payload: schema.RefreshRequest, db: Session = Depends(get_db)):
    user = auth.verify_refresh_token(db, payload.refresh_token)
    auth.revoke_refresh_token(db, payload.refresh_token)  # rotate
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    new_refresh_token = auth.create_refresh_token(db, user.id)
    return schema.TokenResponse(access_token=access_token, refresh_token=new_refresh_token, user=user)


@api.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: schema.RefreshRequest, db: Session = Depends(get_db)):
    auth.revoke_refresh_token(db, payload.refresh_token)


@api.get("/me", response_model=schema.UserResponse)
def read_me(current_user: model.User = Depends(auth.get_current_user)):
    return current_user


# ============================================================
# PRODUCTS — admin manages catalog, everyone can browse it
# ============================================================

@api.post("/product", response_model=schema.CreateProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product: schema.CreateProductRequest,
    db: Session = Depends(get_db),
    admin: model.User = Depends(auth.get_current_admin),
):
    existing = db.query(model.Product).filter(model.Product.name == product.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Product already exists")
    db_product = model.Product(
        name=product.name,
        description=product.description,
        price=product.price,
        quantity=product.quantity,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@api.get("/product", response_model=List[schema.CreateProductResponse])
def get_all_products(db: Session = Depends(get_db)):
    return db.query(model.Product).all()


@api.delete("/product/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin: model.User = Depends(auth.get_current_admin),
):
    db_product = db.query(model.Product).filter(model.Product.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(db_product)
    db.commit()


# ============================================================
# ORDERS — customers place orders, admin can see every order
# ============================================================

@api.post("/order", response_model=schema.CreateOrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order: schema.CreateOrderRequest,
    db: Session = Depends(get_db),
    customer: model.User = Depends(auth.get_current_customer),
):
    db_product = db.query(model.Product).filter(model.Product.id == order.product_id).first()
    if not db_product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if db_product.quantity < order.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not enough stock available")

    db_product.quantity -= order.quantity
    db_order = model.Order(
        product_id=db_product.id,
        product_name=db_product.name,
        customer_id=customer.id,
        quantity=order.quantity,
        total_price=round(db_product.price * order.quantity, 2),
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)

    return schema.CreateOrderResponse(
        id=db_order.id,
        product_id=db_product.id,
        product_name=db_product.name,
        quantity=db_order.quantity,
        total_price=db_order.total_price,
        status=db_order.status,
        created_at=db_order.created_at,
        shipped_at=db_order.shipped_at,
        delivered_at=db_order.delivered_at,
        customer_username=customer.username,
    )


@api.get("/order", response_model=List[schema.CreateOrderResponse])
def get_orders(
    db: Session = Depends(get_db),
    current_user: model.User = Depends(auth.get_current_user),
):
    query = db.query(model.Order)
    if current_user.role == "customer":
        query = query.filter(model.Order.customer_id == current_user.id)
    orders = query.order_by(model.Order.created_at.desc()).all()

    return [
        schema.CreateOrderResponse(
            id=o.id,
            product_id=o.product_id,          # None if that product was later removed
            product_name=o.product_name,       # snapshot, always available
            quantity=o.quantity,
            total_price=o.total_price,
            status=o.status,
            created_at=o.created_at,
            shipped_at=o.shipped_at,
            delivered_at=o.delivered_at,
            customer_username=o.customer.username,
        )
        for o in orders
    ]


def _order_response(o: model.Order) -> schema.CreateOrderResponse:
    return schema.CreateOrderResponse(
        id=o.id,
        product_id=o.product_id,
        product_name=o.product_name,
        quantity=o.quantity,
        total_price=o.total_price,
        status=o.status,
        created_at=o.created_at,
        shipped_at=o.shipped_at,
        delivered_at=o.delivered_at,
        customer_username=o.customer.username,
    )


@api.delete("/order/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    customer: model.User = Depends(auth.get_current_customer),
):
    """Buyer removes/cancels an order that hasn't shipped yet, restocking it."""
    db_order = db.query(model.Order).filter(
        model.Order.id == order_id,
        model.Order.customer_id == customer.id,
    ).first()
    if not db_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if db_order.status != "placed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only an order that hasn't shipped yet can be removed",
        )
    if db_order.product_id:
        db_product = db.query(model.Product).filter(model.Product.id == db_order.product_id).first()
        if db_product:
            db_product.quantity += db_order.quantity
    db.delete(db_order)
    db.commit()


@api.patch("/order/{order_id}/ship", response_model=schema.CreateOrderResponse)
def ship_order(
    order_id: int,
    db: Session = Depends(get_db),
    admin: model.User = Depends(auth.get_current_admin),
):
    """Seller marks an order as sent."""
    db_order = db.query(model.Order).filter(model.Order.id == order_id).first()
    if not db_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if db_order.status != "placed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order is already '{db_order.status}', can't ship it again",
        )
    db_order.status = "shipped"
    db_order.shipped_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_order)
    return _order_response(db_order)


@api.patch("/order/{order_id}/deliver", response_model=schema.CreateOrderResponse)
def deliver_order(
    order_id: int,
    db: Session = Depends(get_db),
    customer: model.User = Depends(auth.get_current_customer),
):
    """Buyer confirms they've received the order."""
    db_order = db.query(model.Order).filter(
        model.Order.id == order_id,
        model.Order.customer_id == customer.id,
    ).first()
    if not db_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if db_order.status != "shipped":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order must be sent by the seller before it can be marked delivered",
        )
    db_order.status = "delivered"
    db_order.delivered_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_order)
    return _order_response(db_order)


# Mount the versioned API under /api, then serve the static frontend at "/".
# Because /api is matched first, opening the site in a browser shows the
# storefront — the API underneath is invisible unless you look at Network tab.
app.mount("/api", api)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
