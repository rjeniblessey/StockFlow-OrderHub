# Stockroom — E-commerce with separate Admin & Customer accounts

A small FastAPI backend + a static HTML/CSS/JS storefront. Run one command,
open the site — the backend runs invisibly behind it.

```
ecommerce-project/
├── backend/
│   ├── main.py          # FastAPI app: auth, product, order routes + serves the frontend
│   ├── database.py      # SQLAlchemy engine/session (SQLite by default, MySQL optional)
│   ├── model.py         # User, RefreshToken, Product, Order tables
│   ├── schema.py        # Pydantic request/response models
│   ├── auth.py          # password hashing, JWT, role-based dependencies
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── index.html        # auth screen + admin/customer dashboards
    ├── style.css          # "market ledger" visual design
    └── app.js             # talks to the API, renders both dashboards
```

## How the roles work

- **Signup** takes a username, email and password, same as a normal shop —
  but there are two completely separate pools of accounts: one for **sellers
  (admin)** and one for **buyers (customer)**. Signing up as a seller and
  signing up as a buyer with the same username both succeed, because they're
  different tables/rows scoped by role — but usernames/emails must still be
  unique per role.
- **Sellers (admin)** can add products and remove them from the shelf. They
  can see every order placed by every buyer.
- **Buyers (customer)** can browse the shelf and place orders. They only see
  their own order history.
- Every product/order route checks the JWT's role server-side
  (`get_current_admin` / `get_current_customer` in `auth.py`) — a buyer token
  can never call the "add product" route, even by hitting the API directly.

## Run it

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit SECRET_KEY at minimum
uvicorn main:app --reload
```

Open **http://localhost:8000** — that's it. You'll see the storefront
(`frontend/index.html`), not any code or API docs. The API itself lives
under `http://localhost:8000/api/...` and interactive docs are still
available at `http://localhost:8000/api/docs` if you ever want to poke it
directly, but nothing links to that from the storefront.

### Using MySQL instead of SQLite

By default the app creates a local `ecommerce.db` SQLite file — zero setup.
To use MySQL instead, set in `.env`:

```
DB_ENGINE=mysql
DB_USER=root
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=e_commerce
```

(Create the `e_commerce` database in MySQL first — the app only creates
tables inside it, not the database itself.)

## API summary

| Method | Path                     | Who           | What |
|--------|--------------------------|---------------|------|
| POST   | `/api/signup/admin`      | anyone        | create a seller account |
| POST   | `/api/signup/customer`   | anyone        | create a buyer account |
| POST   | `/api/login/admin`       | anyone        | log in as seller → tokens |
| POST   | `/api/login/customer`    | anyone        | log in as buyer → tokens |
| POST   | `/api/refresh`           | anyone w/ refresh token | rotate access token |
| POST   | `/api/logout`            | anyone        | revoke a refresh token |
| GET    | `/api/me`                | logged in     | current user info |
| GET    | `/api/product`           | public        | list products |
| POST   | `/api/product`           | admin only    | add a product |
| DELETE | `/api/product/{id}`      | admin only    | remove a product |
| GET    | `/api/order`             | logged in     | admin: all orders · customer: own orders |
| POST   | `/api/order`             | customer only | place an order (checks & decrements stock) |
| DELETE | `/api/order/{id}`        | customer only | remove/cancel an order that hasn't shipped yet (restocks it) |
| PATCH  | `/api/order/{id}/ship`   | admin only    | mark an order as sent |
| PATCH  | `/api/order/{id}/deliver`| customer only | confirm receipt of an order |

## Order lifecycle

Every order moves through three states:

`placed` → seller clicks **Send order** → `shipped` → buyer clicks **Mark received** → `delivered`

- While an order is still `placed`, the buyer can click **Remove** to cancel it — the
  stock goes back on the shelf.
- Once `delivered`, the order drops out of the active "All orders" / "Your receipts"
  list on both dashboards and shows up in a separate **Delivered** section instead,
  so completed orders don't clutter the working list but nothing is lost.

## Design notes

The storefront leans on a "market ledger" idea: kraft-paper background,
price-tag shaped role tabs on the login screen, a Fraunces display serif for
headings, and receipt-style dashed dividers for order/stock lists — a nod to
a real shop counter rather than a generic SaaS dashboard.
