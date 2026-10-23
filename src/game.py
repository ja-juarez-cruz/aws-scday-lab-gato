"""Reglas del Gato. Funciones puras: no saben nada de AWS ni de WebSockets."""

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
    """¿Qué ficha juega esta conexión? "X", "O" o None."""
    if game.get("player_x") == connection_id:
        return "X"
    if game.get("player_o") == connection_id:
        return "O"
    return None


def apply_move(game: dict, connection_id: str, cell) -> tuple[dict | None, str | None]:
    """Aplica una jugada. Regresa (juego_actualizado, None) o (None, mensaje_de_error)."""
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
    """Mensaje de estado para UN jugador: igual para ambos, salvo el campo "you"."""
    return {
        "type": "state",
        "board": game["board"],
        "turn": game["turn"],
        "winner": game.get("winner"),
        "you": seat,
        "players": sum(1 for key in ("player_x", "player_o") if game.get(key)),
    }
