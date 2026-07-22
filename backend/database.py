import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

# --- Build the database URL from environment variables -------------------
# Falls back to a local SQLite file if no MySQL settings are provided, so
# the project runs out of the box with zero setup.

DB_ENGINE = os.getenv("DB_ENGINE", "sqlite")  # "mysql" or "sqlite"

if DB_ENGINE == "mysql":
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = quote_plus(os.getenv("DB_PASSWORD", ""))
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "e_commerce")
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ecommerce.db")
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# communicate with database
sessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# create database model like table
Base = declarative_base()


def get_db():
    db = sessionLocal()
    try:
        yield db
    finally:
        db.close()
