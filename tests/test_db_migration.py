"""Compatibility migration tests for existing installations."""

from sqlalchemy import create_engine, inspect, text

from app.db.session import init_database


def test_init_database_adds_project_scope_to_legacy_memories_table() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE memories ("
                "id VARCHAR(36) PRIMARY KEY, "
                "user_id VARCHAR(128) NOT NULL, "
                "status VARCHAR(24) NOT NULL"
                ")"
            )
        )

    init_database(engine)

    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("memories")}
    indexes = {index["name"] for index in inspector.get_indexes("memories")}
    assert "project_path" in columns
    assert "idx_memories_user_project_status" in indexes
