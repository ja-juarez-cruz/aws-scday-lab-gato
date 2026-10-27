# Gato en tiempo real con WebSockets en AWS

Lab del workshop **"Tiempo real sin servidores: construye un juego multijugador con WebSockets en AWS"**.

Vas a desplegar el backend de un Gato (tic-tac-toe) para 2 jugadores y a programar la parte que lo hace
funcionar en tiempo real: enviar el estado del juego a ambos jugadores.

```
Navegador ──wss──► API Gateway WebSocket
                     ├─ $connect    → src/connect/connect.py        entra a la sala y se le asigna X u O
                     ├─ join        → src/join/join.py              envía el estado a los jugadores de la sala
                     ├─ move        → src/move/move.py              valida la jugada y avisa a ambos   ← Lab 2
                     └─ $disconnect → src/disconnect/disconnect.py  libera el lugar y avisa al rival
                   Layer compartida → layers/shared/python/         common.py (DynamoDB y WebSocket), game.py (reglas)
                   DynamoDB
                     ├─ Connections   connection_id → room, seat
                     └─ Games         room → board, turn, player_x, player_o, winner
```

## Los mensajes

API Gateway lee el campo `action` de cada mensaje para decidir qué Lambda lo atiende.

```jsonc
// navegador → servidor
{ "action": "join" }
{ "action": "move", "cell": 4 }          // casillas 0..8, de izquierda a derecha y de arriba abajo

// servidor → navegador
{ "type": "state", "board": "X___O____", "turn": "X", "you": "O", "winner": null, "players": 2 }
{ "type": "error", "message": "No es tu turno" }
{ "type": "opponent_left" }
```

---

## 0. Antes de empezar (solo si usas tu propia cuenta)

Crea un presupuesto de 1 USD para que AWS te avise si algo genera costos:
**Billing and Cost Management → Budgets → Create budget → Zero spend budget** (o *Monthly cost budget* de 1 USD).

## 1. Abre CloudShell

En la consola de AWS, selecciona la región **N. Virginia (us-east-1)** y abre **CloudShell** (icono `>_` arriba a la derecha).
CloudShell ya trae AWS CLI, SAM CLI, git, Python y Node.js: no instalas nada.

## 2. Clona el repo

```bash
git clone https://github.com/ja-juarez-cruz/aws-scday-lab-gato.git
cd aws-scday-lab-gato
```

## 3. Lab 1: despliega tu backend

```bash
sam deploy
```

Tarda 1–2 minutos. Al final verás el output **WebSocketUrl**. Guárdalo en una variable:

```bash
WS_URL=$(aws cloudformation describe-stacks --stack-name scday-gato \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketUrl'].OutputValue" --output text)
echo $WS_URL
```

> ¿Comparten una misma cuenta de AWS entre varios equipos? Usa un nombre de stack distinto por equipo:
> `sam deploy --stack-name scday-gato-equipo07` (y el mismo nombre en el comando de arriba).

### 3.1 El WebSocket "desnudo" con wscat

Vas a simular a los dos jugadores con dos pestañas de CloudShell. Sigue el orden; de eso depende lo que ves.

**Pestaña 1 (jugador X).** En la que ya tienes abierta:

```bash
npx -y wscat -c "$WS_URL?room=ABCD"
```

Cuando diga `Connected`, escribe y presiona `Enter`:

```json
{"action":"join"}
```

Recibes `"players": 1` y `"you": "X"`: todavía no hay nadie más en la sala.

**Pestaña 2 (jugador O).** Abre otra pestaña con el botón `+`. Es una terminal nueva, así que vuelve a entrar a la
carpeta y a definir `WS_URL`:

```bash
cd aws-scday-lab-gato
WS_URL=$(aws cloudformation describe-stacks --stack-name scday-gato \
  --query "Stacks[0].Outputs[?OutputKey=='WebSocketUrl'].OutputValue" --output text)
npx -y wscat -c "$WS_URL?room=ABCD"
```

Escribe también `{"action":"join"}`. Ahora mira **las dos** pestañas:

- Las dos recibieron un `state` con `"players": 2`. **La pestaña 1 recibió un mensaje sin haber escrito nada**:
  el servidor le habló primero. Eso es un **broadcast**: `join.py` recorre los jugadores de la sala y le envía
  el estado a cada uno.
- Compara `you`: la pestaña 1 dice `"X"` y la 2 dice `"O"`. Cada quien recibe su propia versión del estado.

> ¿Por qué hace falta el `join` si ya estás conectado? `$connect` todavía no puede enviar mensajes, así que nadie
> se entera de que llegaste hasta que mandas `join`. El frontend lo envía solo al conectarse.

Prueba también (hazlo en menos de 10 minutos, ver la nota de abajo):
- Abrir una **tercera** conexión a la misma sala: `$connect` la rechaza (`Unexpected server response: 403`) porque la sala está llena.
- Enviar `{"action":"move","cell":4}`: ¿pasa algo? Ese es el Lab 2.
- En la pestaña 2 presiona `Ctrl+C`: la pestaña 1 recibe `{"type":"opponent_left"}` gracias a `$disconnect`.
  Usa `Ctrl+C`, **no cierres la pestaña**: CloudShell sigue ejecutando wscat aunque cierres la pestaña, y la
  conexión sigue abierta hasta que API Gateway la cierra por inactividad.

> **`Disconnected (code: 1001, reason: "Going away")`.** API Gateway cierra las conexiones que pasan
> **10 minutos sin mensajes**. Es un límite del servicio, no un error tuyo. Vuelve a conectar con el mismo
> comando `npx -y wscat ...` y manda `join`. En el navegador pasa lo mismo: si dice *Desconectado*, recarga la página.

### 3.2 Juega desde el navegador

Cierra las pestañas de wscat con `Ctrl+C` y, en CloudShell, genera el link del juego ya armado con **tu** WebSocket:

```bash
echo "https://ja-juarez-cruz.github.io/aws-scday-lab-gato/web/?ws=$WS_URL"
```

1. Abre ese link en tu navegador. Arriba verás la **Sala** (se genera sola) y "Jugadores: 1/2".
2. Presiona **"Copiar link para tu rival"** y ábrelo en otra laptop, en un celular o en una ventana de incógnito.
3. En las dos debe decir **"Jugadores: 2/2"**. En el panel derecho ves cada mensaje que sale (↑) y entra (↓) por el socket.

> **Es normal que todavía no puedas jugar.** Si haces clic en una casilla, verás tu `↑ {"action":"move",...}` en el panel,
> pero no llega ninguna respuesta: la Lambda `move` aún no le avisa a nadie. Eso es justo lo que programas en el Lab 2.

Si dice *"No se pudo entrar"*, revisa que el link tenga **tu** `WebSocketUrl`: cada despliegue tiene una URL distinta.
Si acabas de desplegar, espera 1 o 2 minutos y recarga.

## 4. Lab 2: haz que funcione en tiempo real

Las jugadas no llegan a nadie. Aquí **no** basta con correr comandos: vas a **escribir unas líneas de Python** en
`src/move/move.py`, donde dice `TODO`. Los comentarios de los TODOs puedes dejarlos o borrarlos, da igual.

Hay dos formas de enviar mensajes desde el servidor, y vas a usar las dos:

- **Unicast:** a una sola conexión. Por ejemplo, el error "No es tu turno" solo le interesa a quien se equivocó.
- **Broadcast:** a todos los de la sala. El tablero nuevo lo tienen que ver los dos jugadores.

En los dos casos se usa `client.post_to_connection(ConnectionId=..., Data=...)`. Lo único que cambia es a quién se lo envías.

### 4.1 Mira el ejemplo

`src/join/join.py` ya hace un broadcast. Este es su `for`: recorre los dos lugares de la sala (X y O) y a cada
jugador le envía su propia versión del estado. Lo vas a copiar tal cual en el TODO 3.

```python
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
```

### 4.2 Abre el archivo

Elige **una** de las dos opciones.

#### Opción A (recomendada): el editor de la consola de Lambda

Es un editor como VS Code dentro del navegador: copias y pegas con el mouse, deshaces con `Ctrl+Z` (`Cmd+Z` en Mac)
y te marca en rojo los errores. En CloudShell, genera el link directo a tu función:

```bash
echo "https://us-east-1.console.aws.amazon.com/lambda/home?region=us-east-1#/functions/$(aws cloudformation describe-stack-resource \
  --stack-name scday-gato --logical-resource-id MoveFunction \
  --query StackResourceDetail.PhysicalResourceId --output text)?tab=code"
```

Abre el link y, a la izquierda, abre `move.py`. Cada Lambda trae solo su archivo; el código que comparten
(`common.py` y `game.py`) le llega por una *Layer*, así que no lo vas a ver aquí.

> Los cambios que hagas aquí viven solo en la Lambda, no en tu carpeta de CloudShell. Si después corres `sam deploy`
> (por ejemplo, en los retos), se sobrescriben con la versión de CloudShell. Si quieres conservarlos, haz también
> los cambios en CloudShell con la opción B.

#### Opción B: `nano` en CloudShell

```bash
nano src/move/move.py
```

| Para | Presiona |
|---|---|
| Moverte | Flechas |
| Pegar lo que copiaste con el mouse | `Ctrl+Shift+V` (`Cmd+V` en Mac) o clic derecho → Pegar |
| **Deshacer** / rehacer | `Alt+U` / `Alt+E` |
| Borrar la línea completa | `Ctrl+K` |
| Buscar texto (por ejemplo `TODO`) | `Ctrl+W` |
| Guardar | `Ctrl+O` y luego `Enter` |
| Salir | `Ctrl+X` |

> En Mac, si `Alt+U` escribe un carácter raro en lugar de deshacer, presiona `Esc` y después `U`
> (lo mismo con `Esc` y `E` para rehacer). En nano, `Esc` + tecla equivale a `Alt` + tecla.
>
> ¿Lo arruinaste? Sal sin guardar (`Ctrl+X` y luego `N`) o recupera el archivo original con
> `git checkout src/move/move.py`.

### 4.3 Completa los 3 TODOs

| TODO | Qué hace | Qué escribes |
|---|---|---|
| 1 | Averigua de qué sala es la conexión que envió el mensaje | Cambia `connection = None` por `connection = get_connection(connection_id)` |
| 2 | **Unicast:** si la jugada no es válida, avísale solo a quien la envió | Un `client.post_to_connection(...)` con `ConnectionId=connection_id` y el mensaje `{"type": "error", "message": error}` |
| 3 | **Broadcast:** envía el tablero nuevo a los dos jugadores | Pega el `for` del paso 4.1 tal cual, sin cambiarle nada |

Cuida la **indentación** (los espacios al inicio de cada línea): en Python indican qué va dentro de qué.
El código del TODO 2 va dentro del `if error:` (8 espacios) y el `for` del TODO 3 va alineado con el `return` final (4 espacios).

<details>
<summary>¿Te atoraste? Ver cómo debe quedar</summary>

```python
    # 1. ¿De qué sala es esta conexión?
    connection = get_connection(connection_id)
    if connection is None:
        print("No encontré la conexión en la tabla Connections")
        return {"statusCode": 403}

    # ... (lo de en medio no cambia) ...

    if error:
        print(f"Jugada rechazada: {error}")
        # Solo a quien envió la jugada (unicast)
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=to_bytes({"type": "error", "message": error}),
        )
        return {"statusCode": 400}

    # 3. Enviamos el nuevo estado a los dos jugadores (broadcast)
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
            remove_connection(player_connection)

    return {"statusCode": 200}
```

</details>

### 4.4 Despliega y prueba

**Si usaste la opción A (consola de Lambda):** guarda con `Ctrl+S` (`Cmd+S` en Mac) y presiona el botón **Deploy**.
Tarda unos segundos.

**Si usaste la opción B (nano):** revisa que no haya errores de sintaxis (si no imprime nada, está bien) y despliega.
Solo cambia el código de la Lambda, así que tarda menos de un minuto:

```bash
python3 -m py_compile src/move/move.py
sam deploy
```

**Recarga las dos ventanas del juego** y juega: ahora cada jugada aparece en las dos, y en el panel ves el `↓ state`
que le llega a cada una. Para probar el TODO 2, en wscat manda una jugada cuando no es tu turno: solo tú recibes el `error`.

### 4.5 ¿No pasa nada? Revisa los logs

Si mandas una jugada y no llega nada, la Lambda te dice por qué en sus logs (cada `print` del código aparece ahí):

- En la consola de Lambda: pestaña **Monitor** → **View CloudWatch logs** → el registro más reciente.
- En CloudShell:

  ```bash
  sam logs --stack-name scday-gato -n MoveFunction --tail
  ```

Por ejemplo, si ves *"No encontré la conexión en la tabla Connections"*, te falta el TODO 1.

### ¿Te atrasaste?

```bash
git stash                     # guarda tus cambios por si quieres volver a ellos
git checkout lab2-solution
sam deploy
```

## 5. Retos extra

El frontend ya tiene botones de **Revancha** y **emotes** (👏 😂 😱 🔥). Envían
`{"action":"rematch"}` y `{"action":"emote","emoji":"🔥"}`, pero esas rutas todavía no existen.
Mientras no existan, verás en el panel de mensajes la respuesta `Forbidden` de API Gateway.

Cada reto es una **ruta nueva**, y una ruta nueva siempre lleva lo mismo:

1. Su código: una carpeta `src/<ruta>/` con su archivo `<ruta>.py`.
2. En `template.yaml`, las 4 piezas: Function, Integration, Route y Permission.
3. Agregarla al `DependsOn` de `GatoStage`.
4. `sam deploy`.

> **¿Sin tiempo?** Salta al [atajo del paso 5.3](#53-atajo-trae-la-solución-con-git-merge): un `git merge` y un
> `sam deploy`, y tienes los dos retos funcionando.

> **Si hiciste el Lab 2 en la consola de Lambda (opción A):** tu `move.py` de CloudShell todavía tiene los TODOs, y
> el `sam deploy` de los retos lo va a sobrescribir en AWS. Antes de desplegar, haz los mismos cambios en
> `src/move/move.py` con nano o usa el atajo del 5.3, que ya trae `move.py` resuelto.

### 5.1 Reto 1: emotes (el más fácil, puro broadcast)

**Paso 1. Crea el archivo.**

```bash
mkdir -p src/emote
nano src/emote/emote.py
```

Pega este punto de partida y completa los pasos 1 a 3 de los comentarios:

```python
"""Ruta "emote": reenvía un emoji a los dos jugadores de la sala."""

import json

from common import get_connection, get_game, remove_connection, to_bytes, ws_client

ALLOWED = {"👏", "😂", "😱", "🔥"}


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    emoji = json.loads(event.get("body") or "{}").get("emoji")
    if emoji not in ALLOWED:
        return {"statusCode": 400}

    # 1. Busca la conexión, igual que en el TODO 1 de move.py (si es None, regresa 403)
    # 2. Trae la partida con get_game(connection["room"])
    # 3. Envía a los dos jugadores el mismo mensaje (broadcast):
    #    {"type": "emote", "emoji": emoji, "from": connection["seat"]}
    #    Pista: el for de join.py, pero aquí todos reciben el mismo mensaje

    return {"statusCode": 200}
```

<details>
<summary>Ver la solución de emote.py</summary>

```python
"""Reto extra - ruta "emote": reenvía un emoji a todos los de la sala. Puro broadcast, sin reglas.

Mensaje que llega:  {"action": "emote", "emoji": "🔥"}
Mensaje que sale:   {"type": "emote", "emoji": "🔥", "from": "X"} a AMBOS jugadores.
"""

import json

from common import get_connection, get_game, remove_connection, to_bytes, ws_client

ALLOWED = {"👏", "😂", "😱", "🔥"}


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]
    emoji = json.loads(event.get("body") or "{}").get("emoji")
    if emoji not in ALLOWED:
        return {"statusCode": 400}

    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    game = get_game(connection["room"])
    message = to_bytes({"type": "emote", "emoji": emoji, "from": connection["seat"]})

    client = ws_client(event)
    for player_connection in (game.get("player_x"), game.get("player_o")):
        if not player_connection:
            continue
        try:
            client.post_to_connection(ConnectionId=player_connection, Data=message)
        except client.exceptions.GoneException:
            remove_connection(player_connection)

    return {"statusCode": 200}
```

</details>

**Paso 2. Agrega las 4 piezas al template.** Abre `nano template.yaml`, baja hasta el final (`Alt+/`, o `Esc` y
luego `/`) y pega este bloque **justo antes** de la línea que empieza con `# Lo que imprime`. El bloque ya trae los
2 espacios del inicio, igual que los demás recursos: no los quites. Es el bloque de `move` con 4 cambios: los nombres (`Emote...`), el `Handler`, el `CodeUri`
y el `RouteKey`.

```yaml
  # ── Reto extra - emote: {"action":"emote","emoji":"🔥"} ─────────────────────
  # Reenvía un emoji a los dos jugadores. Es puro broadcast, sin reglas del juego.
  EmoteFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: emote.handler
      CodeUri: src/emote/
      Policies:
        - DynamoDBCrudPolicy: { TableName: !Ref GamesTable }
        - DynamoDBCrudPolicy: { TableName: !Ref ConnectionsTable }
        - Statement:
            - Effect: Allow
              Action: execute-api:ManageConnections
              Resource: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${GatoApi}/*
  EmoteIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref GatoApi
      IntegrationType: AWS_PROXY
      IntegrationUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${EmoteFunction.Arn}/invocations
  EmoteRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref GatoApi
      RouteKey: emote
      Target: !Sub integrations/${EmoteIntegration}
  EmotePermission:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref EmoteFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${GatoApi}/*
```

**Paso 3. Agrega la ruta al `DependsOn` de `GatoStage`** (busca `DependsOn` con `Ctrl+W`):

```yaml
    DependsOn: [ConnectRoute, DisconnectRoute, JoinRoute, MoveRoute, EmoteRoute]
```

**Paso 4. Despliega y prueba.**

```bash
sam deploy
```

Espera 1 o 2 minutos después del deploy (API Gateway tarda en publicar las rutas nuevas; mientras tanto puedes
seguir viendo `Forbidden`), **recarga las dos ventanas** y presiona un emoji: debe flotar en las dos.

### 5.2 Reto 2: revancha (reinicia el tablero)

Los mismos 4 pasos, con `rematch` en lugar de `emote`:

```bash
mkdir -p src/rematch
nano src/rematch/rematch.py
```

Reglas: solo se puede pedir revancha cuando la partida terminó (`game["winner"]` tiene valor), el tablero se vacía
con `new_board()`, empieza quien perdió y los dos reciben el nuevo `state`.

```python
"""Ruta "rematch": reinicia el tablero cuando la partida ya terminó."""

from common import get_connection, get_game, remove_connection, save_game, to_bytes, ws_client
from game import new_board, state_for


def handler(event, context):
    connection_id = event["requestContext"]["connectionId"]

    # 1. Busca la conexión (si es None, regresa 403) y trae la partida con get_game(...)
    # 2. Si la partida no ha terminado (not game.get("winner")), regresa 400
    # 3. Guarda el tablero anterior y arma la partida nueva:
    #      previous_board = game["board"]
    #      first = "O" if game["winner"] == "X" else "X"
    #      game = {**game, "board": new_board(), "turn": first, "winner": None}
    #    Guárdala con save_game(game, previous_board=previous_board); si regresa False, regresa 409
    #    (significa que el otro jugador ya pidió la revancha)
    # 4. Broadcast: copia el for de join.py tal cual (necesitas client = ws_client(event))

    return {"statusCode": 200}
```

<details>
<summary>Ver la solución de rematch.py</summary>

```python
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
```

</details>

En `template.yaml`, pega este bloque también antes de la línea `# Lo que imprime`:

```yaml
  # ── Reto extra - rematch: {"action":"rematch"} ─────────────────────────────
  # Reinicia el tablero cuando la partida terminó. Son las mismas 4 piezas que move.
  RematchFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: rematch.handler
      CodeUri: src/rematch/
      Policies:
        - DynamoDBCrudPolicy: { TableName: !Ref GamesTable }
        - DynamoDBCrudPolicy: { TableName: !Ref ConnectionsTable }
        - Statement:
            - Effect: Allow
              Action: execute-api:ManageConnections
              Resource: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${GatoApi}/*
  RematchIntegration:
    Type: AWS::ApiGatewayV2::Integration
    Properties:
      ApiId: !Ref GatoApi
      IntegrationType: AWS_PROXY
      IntegrationUri: !Sub arn:aws:apigateway:${AWS::Region}:lambda:path/2015-03-31/functions/${RematchFunction.Arn}/invocations
  RematchRoute:
    Type: AWS::ApiGatewayV2::Route
    Properties:
      ApiId: !Ref GatoApi
      RouteKey: rematch
      Target: !Sub integrations/${RematchIntegration}
  RematchPermission:
    Type: AWS::Lambda::Permission
    Properties:
      Action: lambda:InvokeFunction
      FunctionName: !Ref RematchFunction
      Principal: apigateway.amazonaws.com
      SourceArn: !Sub arn:aws:execute-api:${AWS::Region}:${AWS::AccountId}:${GatoApi}/*
```

Y deja el `DependsOn` así:

```yaml
    DependsOn: [ConnectRoute, DisconnectRoute, JoinRoute, MoveRoute, RematchRoute, EmoteRoute]
```

Despliega con `sam deploy`, espera 1 o 2 minutos, recarga, termina una partida y presiona **Revancha**.

> ¿Algo falla? `sam deploy` te dice si el template tiene un error (casi siempre es la indentación). Si el deploy pasa
> pero el botón no hace nada, revisa los logs: `sam logs --stack-name scday-gato -n RematchFunction --tail`.

### 5.3 Atajo: trae la solución con `git merge`

La rama `retos-solution` tiene todo resuelto: `move.py` del Lab 2, los dos retos y el template con sus rutas.

```bash
git stash                          # guarda tus cambios (si no cambiaste nada, no pasa nada)
git merge origin/retos-solution    # trae la solución
sam deploy
```

Espera 1 o 2 minutos, recarga las dos ventanas y prueba los emotes y la revancha. Después compara con lo que
habías hecho: `git stash show -p` muestra tus cambios guardados.

## 6. Limpieza

Borra todo lo que creaste (no se cobra nada después):

```bash
sam delete --no-prompts
```

---

## Para el instructor

- **Ramas:** `main` (inicio del lab, con TODOs), `lab2-solution` y `retos-solution`.
- **Frontend:** `web/index.html` es un archivo estático sin dependencias. Publícalo con GitHub Pages
  (Settings → Pages → rama `main`, carpeta `/root`) y actualiza la URL del paso 3.2.
- **Pruebas locales** (no hace falta AWS):

  ```bash
  python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
  .venv/bin/pytest            # en main, test_flow falla hasta completar el Lab 2
  .venv/bin/cfn-lint template.yaml
  ```

- **Costo:** con unas cuantas partidas el lab cuesta centavos (Lambda, API Gateway y DynamoDB on-demand),
  y gran parte cae en el Free Tier. La stage limita a 20 mensajes por segundo (ráfagas de 50).
