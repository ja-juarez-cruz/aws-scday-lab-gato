"""Reglas del Gato. Funciones puras: no saben nada de AWS ni de WebSockets.

El tablero (board) es un texto de 9 caracteres, uno por casilla, leído por filas:

    Posiciones:         "X_O_X___O" se ve así:

     0 | 1 | 2           X |   | O
    ---+---+---         ---+---+---
     3 | 4 | 5             | X |
    ---+---+---         ---+---+---
     6 | 7 | 8             |   | O

Cada casilla vale "X", "O" o "_" (vacía). El número de casilla ("cell" en el mensaje
{"action": "move", "cell": 4}) es la posición dentro del texto.

game es el diccionario de la tabla Games (ver common.py): board, turn, winner,
player_x y player_o. seat es la ficha de un jugador, "X" u "O".
"""

EMPTY = "_"
LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # filas
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # columnas
    (0, 4, 8), (2, 4, 6),             # diagonales
]


def new_board() -> str:
    return EMPTY * 9


def winner(board: str) -> str | None:
    """Regresa "X", "O", "draw" (empate) o None si la partida sigue."""
    for a, b, c in LINES:
        if board[a] != EMPTY and board[a] == board[b] == board[c]:
            return board[a]
    if EMPTY not in board:
        return "draw"
    return None


def seat_of(game: dict, connection_id: str) -> str | None:
    """¿Qué ficha juega esta conexión? "X", "O" o None.

    Compara el connection_id contra los asientos de la partida (player_x y player_o).
    """
    if game.get("player_x") == connection_id:
        return "X"
    if game.get("player_o") == connection_id:
        return "O"
    return None


def apply_move(game: dict, connection_id: str, cell) -> tuple[dict | None, str | None]:
    """Aplica una jugada. Regresa (juego_actualizado, None) o (None, mensaje_de_error).

    No modifica el game que recibe: regresa uno nuevo con la casilla marcada, el turno
    pasado a la otra ficha y el winner recalculado.
    """
    seat = seat_of(game, connection_id)
    if seat is None:
        return None, "No estás en esta sala"
    if not (game.get("player_x") and game.get("player_o")):
        return None, "Espera a que llegue tu rival"
    if game.get("winner"):
        return None, "La partida ya terminó"
    if game["turn"] != seat:
        return None, "No es tu turno"
    if isinstance(cell, bool) or not isinstance(cell, int) or not 0 <= cell <= 8:
        return None, "Casilla inválida"

    board = game["board"]
    if board[cell] != EMPTY:
        return None, "Esa casilla ya está ocupada"

    board = board[:cell] + seat + board[cell + 1:]
    return {
        **game,
        "board": board,
        "turn": "O" if seat == "X" else "X",
        "winner": winner(board),
    }, None


def state_for(game: dict, seat: str) -> dict:
    """Mensaje de estado para UN jugador: igual para ambos, salvo el campo "you".

    seat es la ficha de quien VA A RECIBIR el mensaje, no la de quien jugó. Así el
    navegador sabe si "turn" es su turno y si "winner" significa que ganó o perdió.
    "players" cuenta cuántos asientos están ocupados (0, 1 o 2).
    """
    return {
        "type": "state",
        "board": game["board"],
        "turn": game["turn"],
        "winner": game.get("winner"),
        "you": seat,
        "players": sum(1 for key in ("player_x", "player_o") if game.get(key)),
    }
