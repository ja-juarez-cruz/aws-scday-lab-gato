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
    # TODO 1: busca la conexión en la tabla Connections.
    #         Pista: get_connection(connection_id) regresa {"room": ..., "seat": ...} o None
    connection = None
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
    # TODO 2: por cada jugador de la sala, envíale el estado con post_to_connection.
    #   - Sus conexiones están en updated["player_x"] y updated["player_o"]
    #   - Cada uno recibe su propia versión: state_for(updated, "X") o state_for(updated, "O")
    #   - Envía así: client.post_to_connection(ConnectionId=..., Data=to_bytes(mensaje))
    #   Pista: join.py hace algo muy parecido.
    #
    # TODO 3: si post_to_connection lanza client.exceptions.GoneException,
    #         esa conexión ya se cerró: límpiala con remove_connection(...)

    return {"statusCode": 200}
