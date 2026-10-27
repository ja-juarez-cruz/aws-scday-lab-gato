"""Reto extra - ruta "rematch": reinicia el tablero cuando la partida ya terminó.

Mensaje que llega:  {"action": "rematch"}
Mensaje que sale:   {"type": "state", ...} a AMBOS jugadores.
"""

from common import get_connection, get_game, remove_connection, save_game, to_bytes, ws_client
from game import new_board, state_for


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    game = get_game(connection["room"])
    if not game.get("winner"):
        return {"statusCode": 400}  # solo se puede pedir revancha al terminar

    # Tablero nuevo. Empieza quien perdió: si ganó X, abre O (y viceversa)
    previous_board = game["board"]
    first = "O" if game["winner"] == "X" else "X"
    game = {**game, "board": new_board(), "turn": first, "winner": None}
    if not save_game(game, previous_board=previous_board):
        return {"statusCode": 409}  # el otro jugador ya pidió la revancha

    # Broadcast: el mismo for de join.py
    client = ws_client(event)
    for seat, seat_key in (("X", "player_x"), ("O", "player_o")):
        player_connection = game.get(seat_key)
        if not player_connection:
            continue
        try:
            client.post_to_connection(
                ConnectionId=player_connection,
                Data=to_bytes(state_for(game, seat)),
            )
        except client.exceptions.GoneException:
            # Esa conexión ya se cerró y no nos enteramos: la limpiamos
            remove_connection(player_connection)

    return {"statusCode": 200}
