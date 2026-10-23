from game import apply_move, new_board, state_for, winner


def make_game(board=None, turn="X"):
    return {"room": "ABCD", "board": board or new_board(), "turn": turn,
            "player_x": "cx", "player_o": "co", "winner": None}


def test_winner_detects_rows_columns_diagonals_and_draw():
    assert winner("XXX______") == "X"
    assert winner("O__O__O__") == "O"
    assert winner("X___X___X") == "X"
    assert winner("XOXXOOOXX") == "draw"
    assert winner(new_board()) is None


def test_apply_move_switches_turn():
    game, error = apply_move(make_game(), "cx", 4)
    assert error is None
    assert game["board"] == "____X____"
    assert game["turn"] == "O"


def test_apply_move_rejects_invalid_moves():
    assert apply_move(make_game(), "co", 0)[1] == "No es tu turno"
    assert apply_move(make_game(), "intruso", 0)[1] == "No estás en esta sala"
    assert apply_move(make_game("X________", "O"), "co", 0)[1] == "Esa casilla ya está ocupada"
    assert apply_move(make_game(), "cx", 9)[1] == "Casilla inválida"
    assert apply_move(make_game(), "cx", True)[1] == "Casilla inválida"
    assert apply_move({**make_game(), "player_o": None}, "cx", 0)[1] == "Espera a que llegue tu rival"


def test_apply_move_detects_winner():
    game, _ = apply_move(make_game("XX_OO____"), "cx", 2)
    assert game["winner"] == "X"
    assert apply_move(game, "co", 5)[1] == "La partida ya terminó"


def test_state_for_personalizes_you():
    game = make_game()
    assert state_for(game, "X")["you"] == "X"
    assert state_for(game, "O")["you"] == "O"
    assert state_for(game, "O")["players"] == 2
