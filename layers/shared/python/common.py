"""Acceso a DynamoDB y al canal de regreso del WebSocket, compartido por todos los handlers.

Cómo se relacionan los datos (los mismos nombres se usan en todos los .py):

    connection_id  Id que API Gateway le da a cada WebSocket abierto (uno por pestaña).
                   Es la "dirección" a la que se le escribe con post_to_connection.
    room           Código de la sala (?room=ABCD). Une a los 2 jugadores de una partida.
    seat           La ficha de un jugador: "X" u "O".
    seat_key       El atributo de la tabla Games que guarda el connection_id de esa ficha:
                   "X" -> "player_x" y "O" -> "player_o".

    Tabla Connections, una fila por conexión abierta ("connection" en el código):
        {"connection_id": "abc=", "room": "ABCD", "seat": "X", "expires_at": ...}
        Sirve para responder "¿de qué sala es quien me escribe?" con un solo get_item.

    Tabla Games, una fila por sala ("game" en el código):
        {"room": "ABCD",
         "board": "X_O______",       9 casillas, "_" = vacía (ver game.py)
         "turn": "O",                la ficha (seat) que debe jugar
         "winner": None,             "X", "O", "draw" o None si la partida sigue
         "player_x": "abc=",         connection_id de quien juega con X
         "player_o": "def=",         connection_id de quien juega con O (falta si no ha llegado)
         "expires_at": ...}

    Para ir de un mensaje a la partida: connection_id -> Connections -> room -> Games -> game.
    Para ir de la partida a los jugadores: game["player_x"] y game["player_o"] son los
    connection_id a los que se les envía el estado (broadcast).

    Un mismo dato vive en dos lugares: el seat está en Connections (connection["seat"]) y
    también se deduce de Games (seat_of en game.py). Las reglas usan Games, que es la fuente
    de verdad; Connections solo sirve para encontrar la sala y para limpiar al desconectarse.
"""

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
    """Guarda el tablero solo si nadie más lo cambió mientras tanto.

    previous_board es el tablero que leímos ANTES de aplicar la jugada. Si en DynamoDB ya
    no es ese (por ejemplo, el rival jugó en el mismo instante), no se guarda y regresa False.
    Solo se actualizan board, turn y winner: los asientos (player_x, player_o) no se tocan.
    """
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

    Aquí sí se usa el seat de Connections: es lo que dice qué atributo (player_x o
    player_o) hay que borrar en Games. La condición "#seat = :cid" evita borrar el asiento
    si ya lo ocupa otra conexión.
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
