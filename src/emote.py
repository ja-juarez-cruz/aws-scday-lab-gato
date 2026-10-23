"""Reto extra - ruta "emote": reenvía un emoji a todos los de la sala. Puro broadcast, sin reglas.

Mensaje que llega:  {"action": "emote", "emoji": "🔥"}
Mensaje que sale:   {"type": "emote", "emoji": "🔥", "from": "X"} a AMBOS jugadores.
"""

import json

from common import get_connection, get_game, remove_connection, to_bytes, ws_client

ALLOWED = {"👏", "😂", "😱", "🔥"}


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    emoji = json.loads(event.get("body") or "{}").get("emoji")
    if emoji not in ALLOWED:
        return {"statusCode": 400}

    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    game = get_game(connection["room"])
    message = to_bytes({"type": "emote", "emoji": emoji, "from": connection["seat"]})

    client = ws_client(event)
    for player_connection in (game.get("player_x"), game.get("player_o")):
        if not player_connection:
            continue
        try:
            client.post_to_connection(ConnectionId=player_connection, Data=message)
        except client.exceptions.GoneException:
            remove_connection(player_connection)

    return {"statusCode": 200}
