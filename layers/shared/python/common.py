"""Acceso a DynamoDB y al canal de regreso del WebSocket, compartido por todos los handlers."""

import json
import os
import time

import boto3
from botocore.exceptions import ClientError

from game import new_board

dynamodb = boto3.resource("dynamodb")
games_table = dynamodb.Table(os.environ["GAMES_TABLE"])
connections_table = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])

TTL_SECONDS = 24 * 60 * 60  # DynamoDB borra solo lo que quede de partidas viejas


def expires_at() -> int:
    return int(time.time()) + TTL_SECONDS


def ws_client(event: dict):
    """Cliente para enviar mensajes a las conexiones abiertas de ESTE WebSocket."""
    ctx = event["requestContext"]
    return boto3.client(
        "apigatewaymanagementapi",
        endpoint_url=f"https://{ctx['domainName']}/{ctx['stage']}",
    )


def to_bytes(message: dict) -> bytes:
    return json.dumps(message).encode()


def get_connection(connection_id: str) -> dict | None:
    """Tabla Connections: connectionId -> {room, seat}."""
    return connections_table.get_item(Key={"connection_id": connection_id}).get("Item")


def get_game(room: str) -> dict | None:
    return games_table.get_item(Key={"room": room}).get("Item")


def save_game(game: dict, previous_board: str) -> bool:
    """Guarda el tablero solo si nadie más lo cambió mientras tanto."""
    try:
        games_table.update_item(
            Key={"room": game["room"]},
            UpdateExpression="SET #board = :board, #turn = :turn, #winner = :winner",
            ConditionExpression="#board = :previous",
            ExpressionAttributeNames={"#board": "board", "#turn": "turn", "#winner": "winner"},
            ExpressionAttributeValues={
                ":board": game["board"],
                ":turn": game["turn"],
                ":winner": game.get("winner"),
                ":previous": previous_board,
            },
        )
        return True
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def remove_connection(connection_id: str) -> dict | None:
    """Borra la conexión, libera su lugar y reinicia el tablero.

    Regresa el juego actualizado si queda alguien en la sala, o None si quedó vacía.
    """
    old = connections_table.delete_item(
        Key={"connection_id": connection_id}, ReturnValues="ALL_OLD"
    ).get("Attributes")
    if not old:
        return None

    seat_key = "player_x" if old["seat"] == "X" else "player_o"
    try:
        game = games_table.update_item(
            Key={"room": old["room"]},
            UpdateExpression="REMOVE #seat SET #board = :board, #turn = :x, #winner = :none",
            ConditionExpression="#seat = :cid",
            ExpressionAttributeNames={
                "#seat": seat_key, "#board": "board", "#turn": "turn", "#winner": "winner",
            },
            ExpressionAttributeValues={
                ":cid": connection_id, ":board": new_board(), ":x": "X", ":none": None,
            },
            ReturnValues="ALL_NEW",
        )["Attributes"]
    except ClientError as err:
        if err.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return None
        raise

    if not game.get("player_x") and not game.get("player_o"):
        games_table.delete_item(Key={"room": old["room"]})
        return None
    return game
