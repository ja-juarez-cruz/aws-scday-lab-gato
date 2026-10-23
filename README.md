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
git clone https://github.com/<usuario>/SCDay-lab-gato.git
cd SCDay-lab-gato
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

Abre el frontend con la URL de tu WebSocket:

```
https://<usuario>.github.io/SCDay-lab-gato/web/?ws=<tu WebSocketUrl>
```

Copia el link con el botón **"Copiar link para tu rival"** y ábrelo en otra laptop o celular.
En el panel derecho ves cada mensaje que sale (↑) y entra (↓) por el socket.

## 4. Lab 2: haz que funcione en tiempo real

Las jugadas no llegan a nadie. Abre `src/move.py` y completa los 3 TODOs:

```bash
nano src/move.py        # o el editor que prefieras
```

| TODO | Qué hace | Pista |
|---|---|---|
| 1 | Averigua de qué sala es la conexión que envió el mensaje | `get_connection(connection_id)` |
| 2 | Envía el nuevo estado a **los dos** jugadores, cada uno con su ficha en `you` | `join.py` hace algo muy parecido |
| 3 | Si una conexión ya no existe (`GoneException`), límpiala | `remove_connection(...)` |

Despliega y prueba (solo cambia el código de la Lambda, tarda unos segundos):

```bash
sam deploy
```

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
