"""Ruta "move": un jugador marca una casilla.

Mensaje que llega:  {"action": "move", "cell": 4}
Mensaje que sale:   {"type": "state", ...} a AMBOS jugadores,
                    o {"type": "error", ...} solo a quien se equivocó.
"""

import json

from common import get_connection, get_game, remove_connection, save_game, to_bytes, ws_client
from game import apply_move, state_for


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    body = json.loads(event.get("body") or "{}")
    client = ws_client(event)

    # 1. ¿De qué sala es esta conexión?
    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    # 2. Aplicamos la jugada (las reglas viven en game.py)
    game = get_game(connection["room"])
    updated, error = apply_move(game, connection_id, body.get("cell"))
    if error is None and not save_game(updated, previous_board=game["board"]):
        error = "El tablero cambió, intenta de nuevo"
    if error:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=to_bytes({"type": "error", "message": error}),
        )
        return {"statusCode": 400}

    # 3. Enviamos el nuevo estado a los dos jugadores
    for seat, seat_key in (("X", "player_x"), ("O", "player_o")):
        player_connection = updated.get(seat_key)
        if not player_connection:
            continue
        try:
            client.post_to_connection(
                ConnectionId=player_connection,
                Data=to_bytes(state_for(updated, seat)),
            )
        except client.exceptions.GoneException:
            remove_connection(player_connection)

    return {"statusCode": 200}
