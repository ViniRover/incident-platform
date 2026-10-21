from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def get_session(request: Request) -> Iterator[Session]:
    # Function scope commits before the HTTP response is sent; exceptions roll back.
    with Session(request.app.state.resources.engine, expire_on_commit=False) as session:
        with session.begin():
            yield session


DatabaseSession = Annotated[Session, Depends(get_session, scope="function")]
