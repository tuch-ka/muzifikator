"""Общие фикстуры: временная база, поднятая настоящими миграциями."""

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from muzifikator.config import Settings
from muzifikator.storage import create_session_factory, init_storage


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "data" / "test.sqlite3"


@pytest.fixture
def engine(db_path) -> Iterator[Engine]:
    engine = init_storage(Settings(db_path=db_path))
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    factory = create_session_factory(engine)
    with factory() as session:
        yield session
        session.rollback()
