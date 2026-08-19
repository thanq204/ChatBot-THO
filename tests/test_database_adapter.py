from backend.services.database import PostgresConnection


class FakeCursor:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def execute(self, *args: object) -> None:
        self.calls.append(args)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()

    def cursor(self, **_kwargs: object) -> FakeCursor:
        return self.cursor_instance


def adapter() -> tuple[PostgresConnection, FakeCursor]:
    connection = FakeConnection()
    result = object.__new__(PostgresConnection)
    result._connection = connection
    return result, connection.cursor_instance


def test_execute_does_not_pass_empty_parameters_for_literal_percent() -> None:
    connection, cursor = adapter()
    sql = "SELECT 1 FROM operations_messages WHERE message_id LIKE 'test-%'"

    connection.execute(sql)

    assert cursor.calls == [(sql,)]


def test_execute_translates_qmark_when_parameters_exist() -> None:
    connection, cursor = adapter()

    connection.execute("SELECT 1 FROM app_users WHERE email=?", ("admin@gmail.com",))

    assert cursor.calls == [
        ("SELECT 1 FROM app_users WHERE email=%s", ("admin@gmail.com",)),
    ]
