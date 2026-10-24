# Gato en tiempo real con WebSockets en AWS

Lab del workshop **"Tiempo real sin servidores: construye un juego multijugador con WebSockets en AWS"**.

Vas a desplegar el backend de un Gato (tic-tac-toe) para 2 jugadores y a programar la parte que lo hace
funcionar en tiempo real: enviar el estado del juego a ambos jugadores.

```
Navegador ──wss──► API Gateway WebSocket
                     ├─ $connect    → src/connect.py     entra a la sala y se le asigna X u O
                     ├─ join        → src/join.py        envía el estado a los jugadores de la sala
                     ├─ move        → src/move.py        valida la jugada y avisa a ambos   ← Lab 2
                     └─ $disconnect → src/disconnect.py  libera el lugar y avisa al rival
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

Abre **dos pestañas** de CloudShell (botón `+`). En cada una ejecuta (en la segunda vuelve a hacer `cd` y a definir `WS_URL`):

```bash
npx wscat -c "$WS_URL?room=ABCD"
```

En ambas escribe:

```json
{"action":"join"}
```

Cuando la segunda pestaña hace `join`, **las dos** reciben un mensaje `state`. Eso es un broadcast.

Prueba también:
- Abrir una **tercera** conexión a la misma sala: `$connect` la rechaza con `403` porque la sala está llena.
- Cerrar una pestaña con `Ctrl+C`: la otra recibe `{"type":"opponent_left"}` gracias a `$disconnect`.
- Enviar `{"action":"move","cell":4}`: ¿pasa algo? Ese es el Lab 2.

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
`src/move.py`, donde dice `TODO`. Los comentarios de los TODOs puedes dejarlos o borrarlos, da igual.

### 4.1 Mira el ejemplo

Abre `src/join.py`. Al final tiene un `for` que le envía el estado a cada jugador de la sala. Ese es el patrón del
broadcast y lo vas a repetir en `move.py`:

```bash
cat src/join.py
```

### 4.2 Abre el archivo

```bash
nano src/move.py
```

En `nano` te mueves con las flechas, guardas con `Ctrl+O` y luego `Enter`, y sales con `Ctrl+X`.

### 4.3 Completa los 3 TODOs

| TODO | Qué hace | Qué escribes |
|---|---|---|
| 1 | Averigua de qué sala es la conexión que envió el mensaje | Cambia `connection = None` por `connection = get_connection(connection_id)` |
| 2 | Envía el nuevo estado a **los dos** jugadores, cada uno con su ficha en `you` | Debajo del comentario del TODO 2, pega el `for` de `join.py` y cambia `game` por `updated` |
| 3 | Si una conexión ya no existe (`GoneException`), límpiala | Ya viene en el `for` que copiaste (el `try` / `except`) |

Cuida la **indentación**: en Python, el `for` debe quedar alineado con el `return` de abajo (4 espacios).

<details>
<summary>¿Te atoraste? Ver cómo debe quedar</summary>

```python
    # 1. ¿De qué sala es esta conexión?
    connection = get_connection(connection_id)
    if connection is None:
        return {"statusCode": 403}

    # ... (lo de en medio no cambia) ...

    # 3. Enviamos el nuevo estado a los dos jugadores
    for seat, seat_key in (("X", "player_x"), ("O", "player_o")):
        player_connection = updated.get(seat_key)
        if not player_connection:
            continue
        try:
            client.post_to_connection(
                ConnectionId=player_connection,
                Data=to_bytes(state_for(updated, seat)),
            )
        except client.exceptions.GoneException:
            remove_connection(player_connection)

    return {"statusCode": 200}
```

</details>

### 4.4 Revisa, despliega y prueba

Antes de desplegar, revisa que no haya errores de sintaxis (si no imprime nada, está bien):

```bash
python3 -m py_compile src/move.py
```

Despliega. Solo cambia el código de la Lambda, así que tarda menos de un minuto:

```bash
sam deploy
```

**Recarga las dos ventanas del juego** y juega: ahora cada jugada aparece en las dos, y en el panel ves el `↓ state`
que le llega a cada una.

Para ver los logs de tu Lambda mientras juegas:

```bash
sam logs --stack-name scday-gato -n MoveFunction --tail
```

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

1. **Emotes:** crea `src/emote.py` que reenvíe `{"type":"emote","emoji":...,"from":"X"}` a ambos jugadores.
2. **Revancha:** crea `src/rematch.py` que reinicie el tablero cuando la partida terminó.

Para cada ruta nueva agrega a `template.yaml` una función, una integración, una ruta y un permiso
(copia el bloque de `move` y cambia los nombres), y agrégala al `DependsOn` de `GatoStage`.
La solución está en la rama `retos-solution`.

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
