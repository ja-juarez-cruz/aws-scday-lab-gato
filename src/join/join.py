"""Ruta "join": el cliente la envía en cuanto se abre el socket.

Mensaje que llega:  {"action": "join"}
Mensaje que sale:   {"type": "state", ...} a CADA jugador de la sala.
"""

from common import get_connection, get_game, remove_connection, to_bytes, ws_client
from game import state_for


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    game = get_game(connection["room"])
    client = ws_client(event)

    # Avisamos a todos los de la sala, cada quien con su ficha en "you"
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
