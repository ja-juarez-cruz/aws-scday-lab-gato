# SCDay-lab-gato

Lab de un workshop introductorio de WebSockets en AWS: un Gato (tic-tac-toe) para 2 jugadores.
Los participantes despliegan el backend desde AWS CloudShell y completan los TODOs de `src/move.py`.
El README está escrito para ellos y sigue el orden de la agenda del taller.

## Arquitectura

- API Gateway **WebSocket** (`RouteSelectionExpression: $request.body.action`), stage `lab` con `AutoDeploy`
  y throttling de 20 rps / ráfaga 50.
- Rutas → Lambdas (Python 3.12, arm64, sin dependencias, `CodeUri: src/` compartido):
  - `$connect` → `connect.py`: valida `?room=` (`[A-Z0-9]{3,12}`), toma el asiento X u O con una escritura
    condicional y rechaza con 403 si la sala está llena. Aquí todavía no se pueden enviar mensajes.
  - `join` → `join.py`: envía `state` a cada jugador de la sala. Es el **ejemplo de referencia** de broadcast.
  - `move` → `move.py`: aplica la jugada y envía `state` a ambos, o `error` solo a quien envió.
  - `$disconnect` → `disconnect.py`: libera el asiento, reinicia el tablero y envía `opponent_left`.
  - Retos (solo en la rama `retos-solution`): `rematch` → `rematch.py`, `emote` → `emote.py`.
- DynamoDB on-demand, con TTL `expires_at` de 24 h:
  - `Connections`: `connection_id` → `room`, `seat`.
  - `Games`: `room` → `board` (9 caracteres, `_` = vacío), `turn`, `player_x`, `player_o`, `winner` (`X`/`O`/`draw`/null).
- `src/game.py`: reglas puras (sin AWS). `src/common.py`: tablas, `ws_client(event)` (endpoint
  `https://{domainName}/{stage}`), `save_game` (condicional sobre el tablero anterior) y `remove_connection`.
- `web/index.html`: frontend estático de un solo archivo, sin dependencias. Lee `?ws=` y `?room=`
  (si no hay sala, genera una), muestra un panel con los mensajes ↑/↓ y ya trae los botones de revancha y emotes.

## Protocolo

```
cliente → {"action":"join"} | {"action":"move","cell":0-8} | {"action":"rematch"} | {"action":"emote","emoji":"🔥"}
servidor → {"type":"state","board","turn","you","winner","players"} | {"type":"error","message"}
           | {"type":"opponent_left"} | {"type":"emote","emoji","from"}
```

## Ramas (importante)

- `main`: inicio del Lab 2. `move.py` tiene los TODOs 1–3; `test_flow` falla a propósito en 2 pruebas.
- `lab2-solution` = `main` con `move.py` resuelto.
- `retos-solution` = `lab2-solution` + `rematch.py`, `emote.py`, sus rutas en `template.yaml` y su prueba.

Cualquier cambio en código compartido (`common.py`, `game.py`, `join.py`, `web/`, `README.md`, `template.yaml`)
se hace en `main` y se propaga en cadena: `main` → `lab2-solution` → `retos-solution` (merge o cherry-pick).
Después se corren las pruebas en cada rama.

## Comandos

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest                    # en main: 6 pasan y 2 fallan (esperado); en las soluciones pasan todas
.venv/bin/cfn-lint template.yaml
sam deploy                          # usa samconfig.toml: stack scday-gato, us-east-1
sam delete --no-prompts
```

`sam deploy` funciona **sin** `sam build` a propósito: no hay dependencias, y así CloudShell no necesita Python 3.12.

## Convenciones

- Comentarios, docstrings y mensajes al usuario en español; identificadores en inglés.
- El código es para principiantes: explícito y repetido antes que abstracto. El loop de broadcast se repite
  en cada handler a propósito, para que `join.py` sirva de guía al TODO de `move.py`. No lo factorices.
- Las Lambdas no deben tener dependencias externas (solo boto3, que ya viene en el runtime).
- En los nombres y descripciones de recursos de AWS se usan guiones, nunca guiones largos (em dash).
