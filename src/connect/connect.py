"""Ruta $connect: se ejecuta cuando un navegador abre el WebSocket.

Aquí decidimos si la conexión entra (200) o se rechaza (400/403).
Todavía NO se pueden enviar mensajes: la conexión termina de abrirse
hasta que este handler responde 200.
"""

import re

from botocore.exceptions import ClientError

from common import connections_table, expires_at, games_table
from game import new_board

ROOM_PATTERN = re.compile(r"[A-Z0-9]{3,12}")


def take_seat(room: str, connection_id: str) -> str | None:
    """Intenta sentarse como X y, si está ocupada, como O. None = sala llena."""
    for seat, seat_key in (("X", "player_x"), ("O", "player_o")):
        try:
            games_table.update_item(
                Key={"room": room},
                UpdateExpression=(
                    "SET #seat = :cid, #board = if_not_exists(#board, :board), "
                    "#turn = if_not_exists(#turn, :x), #exp = :exp"
                ),
                ConditionExpression="attribute_not_exists(#seat)",
                ExpressionAttributeNames={
                    "#seat": seat_key, "#board": "board", "#turn": "turn", "#exp": "expires_at",
                },
                ExpressionAttributeValues={
                    ":cid": connection_id, ":board": new_board(), ":x": "X", ":exp": expires_at(),
                },
            )
            return seat
        except ClientError as err:
            if err.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
    return None


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    room = ((event.get("queryStringParameters") or {}).get("room") or "").upper()

    if not ROOM_PATTERN.fullmatch(room):
        print(f"Conexión {connection_id} rechazada: sala inválida {room!r}")
        return {"statusCode": 400}

    seat = take_seat(room, connection_id)
    if seat is None:
        print(f"Conexión {connection_id} rechazada: la sala {room} está llena")
        return {"statusCode": 403}

    # Guardamos de qué sala es esta conexión para encontrarla en los demás mensajes
    connections_table.put_item(Item={
        "connection_id": connection_id,
        "room": room,
        "seat": seat,
        "expires_at": expires_at(),
    })
    print(f"Conexión {connection_id} entró a la sala {room} como {seat}")
    return {"statusCode": 200}
