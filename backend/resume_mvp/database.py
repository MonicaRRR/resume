from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def create_database(path: Path) -> sessionmaker[Session]:
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{path}",
        connect_args={"check_same_thread": False},
    )

    from resume_mvp import tables  # noqa: F401

    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        project_columns = {
            column["name"] for column in inspect(connection).get_columns("projects")
        }
        if "application_type" not in project_columns:
            connection.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN application_type "
                    "VARCHAR(20) NOT NULL DEFAULT 'experienced'"
                )
            )
    return sessionmaker(bind=engine, expire_on_commit=False)
