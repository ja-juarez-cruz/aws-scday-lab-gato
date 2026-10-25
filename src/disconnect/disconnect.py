"""Ruta $disconnect: se ejecuta cuando una conexión se cierra (pestaña cerrada, wifi caído...).

Ya no le podemos escribir a quien se fue, pero sí avisarle a su rival.
"""

from common import remove_connection, to_bytes, ws_client


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    game = remove_connection(connection_id)  # libera el lugar y reinicia el tablero
    if game is None:
        return {"statusCode": 200}  # la sala quedó vacía, no hay a quién avisar

    client = ws_client(event)
    for player_connection in (game.get("player_x"), game.get("player_o")):
        if not player_connection:
            continue
        try:
            client.post_to_connection(
                ConnectionId=player_connection,
                Data=to_bytes({"type": "opponent_left"}),
            )
        except client.exceptions.GoneException:
            pass  # también se fue; su propio $disconnect lo limpiará

    return {"statusCode": 200}
