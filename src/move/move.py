"""Ruta "move": un jugador marca una casilla.

Mensaje que llega:  {"action": "move", "cell": 4}
Mensaje que sale:   {"type": "state", ...} a AMBOS jugadores (broadcast),
                    o {"type": "error", ...} solo a quien se equivocó (unicast).
"""

import json

from common import get_connection, get_game, remove_connection, save_game, to_bytes, ws_client
from game import apply_move, state_for


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    body = json.loads(event.get("body") or "{}")
    client = ws_client(event)
    print(f"Jugada de {connection_id}: {body}")

    # 1. ¿De qué sala es esta conexión?
    # TODO 1: busca la conexión en la tabla Connections.
    #         Pista: get_connection(connection_id) regresa {"room": ..., "seat": ...} o None
    connection = None
    if connection is None:
        print("No encontré la conexión en la tabla Connections (¿ya resolviste el TODO 1?)")
        return {"statusCode": 403}

    # 2. Aplicamos la jugada (las reglas viven en game.py)
    game = get_game(connection["room"])
    previous_board = game["board"]
    game, error = apply_move(game, connection_id, body.get("cell"))
    if error is None and not save_game(game, previous_board=previous_board):
        error = "El tablero cambió, intenta de nuevo"

    if error:
        print(f"Jugada rechazada: {error}")
        # TODO 2: avísale SOLO a quien envió la jugada qué salió mal (unicast).
        #   - El mensaje es {"type": "error", "message": error}
        #   - Envía así: client.post_to_connection(ConnectionId=..., Data=to_bytes(mensaje))
        #   Pista: ¿cuál es el connectionId de quien envió este mensaje?
        return {"statusCode": 400}

    # 3. Enviamos el nuevo estado a los dos jugadores (broadcast)
    # TODO 3: copia aquí el "for" de join.py tal cual; funciona sin cambios.
    #   Recorre los dos lugares de la sala y a cada jugador le envía su versión del estado.

    return {"statusCode": 200}
