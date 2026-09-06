import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://wallet:wallet@localhost:5432/wallet_db",
)


class Base(DeclarativeBase):
    pass


engine_options: dict[str, object] = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)


def crear_tablas() -> None:
    from . import modelos_orm  # noqa: F401

    Base.metadata.create_all(bind=engine)


def obtener_sesion() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
