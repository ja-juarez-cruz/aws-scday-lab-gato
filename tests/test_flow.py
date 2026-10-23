"""Flujo completo con DynamoDB simulado (moto) y un WebSocket falso que guarda lo enviado."""

import importlib
import json
import os

import boto3
import pytest
from moto import mock_aws

os.environ.update({
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "test",
    "GAMES_TABLE": "games",
    "CONNECTIONS_TABLE": "connections",
})


class GoneException(Exception):
    pass


class FakeSocket:
    """Imita al cliente apigatewaymanagementapi."""

    class exceptions:
        GoneException = GoneException

    def __init__(self):
        self.inbox = {}   # connection_id -> [mensajes]
        self.gone = set()

    def post_to_connection(self, ConnectionId, Data):
        if ConnectionId in self.gone:
            raise GoneException()
        self.inbox.setdefault(ConnectionId, []).append(json.loads(Data))

    def last(self, connection_id):
        return self.inbox[connection_id][-1]


@pytest.fixture
def lab(monkeypatch):
    with mock_aws():
        ddb = boto3.client("dynamodb")
        ddb.create_table(TableName="games", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "room", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "room", "KeyType": "HASH"}])
        ddb.create_table(TableName="connections", BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "connection_id", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "connection_id", "KeyType": "HASH"}])

        import common
        importlib.reload(common)
        modules = {}
        for name in ("connect", "join", "move", "disconnect"):
            modules[name] = importlib.reload(importlib.import_module(name))

        socket = FakeSocket()
        for mod in modules.values():
            if hasattr(mod, "ws_client"):
                monkeypatch.setattr(mod, "ws_client", lambda event: socket)
        yield modules, socket


def event(connection_id, room=None, body=None):
    return {
        "requestContext": {"connectionId": connection_id, "domainName": "x", "stage": "lab"},
        "queryStringParameters": {"room": room} if room else None,
        "body": json.dumps(body) if body is not None else None,
    }


def test_two_players_play_a_full_game(lab):
    m, socket = lab
    assert m["connect"].handler(event("cx", "abcd"), None)["statusCode"] == 200
    assert m["connect"].handler(event("co", "ABCD"), None)["statusCode"] == 200
    assert m["connect"].handler(event("c3", "ABCD"), None)["statusCode"] == 403  # sala llena
    assert m["connect"].handler(event("c4", "!"), None)["statusCode"] == 400

    m["join"].handler(event("co", body={"action": "join"}), None)
    assert socket.last("cx")["you"] == "X"
    assert socket.last("co")["you"] == "O"
    assert socket.last("co")["players"] == 2

    # Fuera de turno: solo O recibe el error
    m["move"].handler(event("co", body={"action": "move", "cell": 0}), None)
    assert socket.last("co") == {"type": "error", "message": "No es tu turno"}

    for conn, cell in [("cx", 0), ("co", 3), ("cx", 1), ("co", 4), ("cx", 2)]:
        assert m["move"].handler(event(conn, body={"action": "move", "cell": cell}), None)["statusCode"] == 200

    assert socket.last("cx")["board"] == "XXXOO____"
    assert socket.last("cx")["winner"] == "X"
    assert socket.last("co")["winner"] == "X"


def test_disconnect_notifies_opponent_and_frees_seat(lab):
    m, socket = lab
    m["connect"].handler(event("cx", "ROOM1"), None)
    m["connect"].handler(event("co", "ROOM1"), None)
    m["move"].handler(event("cx", body={"action": "move", "cell": 4}), None)

    m["disconnect"].handler(event("cx"), None)
    assert socket.last("co") == {"type": "opponent_left"}

    # Alguien nuevo entra al lugar libre y el tablero está limpio
    assert m["connect"].handler(event("cnew", "ROOM1"), None)["statusCode"] == 200
    m["join"].handler(event("cnew", body={"action": "join"}), None)
    assert socket.last("cnew")["you"] == "X"
    assert socket.last("cnew")["board"] == "_________"

    # Cuando se van todos, la sala desaparece
    m["disconnect"].handler(event("co"), None)
    m["disconnect"].handler(event("cnew"), None)
    import common
    assert common.get_game("ROOM1") is None


def test_gone_connection_is_cleaned_up(lab):
    m, socket = lab
    m["connect"].handler(event("cx", "ROOM2"), None)
    m["connect"].handler(event("co", "ROOM2"), None)
    socket.gone.add("co")  # O cerró la pestaña y API Gateway aún no lo notificó

    m["move"].handler(event("cx", body={"action": "move", "cell": 0}), None)
    import common
    assert common.get_connection("co") is None
    assert common.get_game("ROOM2").get("player_o") is None

