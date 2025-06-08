from flask_socketio import emit, join_room
from flask import request, session
from datetime import datetime, timedelta
from db import get_db_connection
from flask import request
import sqlite3
import time
import chess
import html

last_heartbeat = {}
message_cooldown = {}
sid_to_user = {}



def register_socketio_events(socketio, room_users, room_lock):

    # Cuando el usuario establece una conexión Socket.IO, el user_id enviado por el front-end se escribe en la sesión Flask en el lado del servidor.
    @socketio.on("connect")
    def on_connect():
        user_id = request.args.get("user_id")
        print("🟡 Socket connect received user_id from query:", user_id)
        session["user_id"] = int(user_id) if user_id else None
        print("🟢 session['user_id'] set to:", session.get("user_id"))


    # Verificar que el jugador autorizado realice el movimiento
    @socketio.on("move_piece")
    def handle_move_piece(data):
        
        player_id = session.get("user_id")
        game_id = str(data.get("game_id"))
        move_uci = data.get("move")  
        fen_client = data.get("fen") 
        my_time = data.get("my_time")
        opponent_time = data.get("opponent_time")   
        board = chess.Board()
        
        # Verificar que la información recibida esté completa
        if not all([game_id, move_uci, fen_client, player_id]):
            emit("error", {"error": "Datos incompletos"})
            return

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT move FROM moves WHERE game_id=%s ORDER BY move_index ASC
            """, (game_id,))
            moves = [row[0] for row in cursor.fetchall()]

        # Obtener el historial completo de movimientos
        try:
            for m in moves:
                board.push_uci(m)
        except Exception as e:
            emit("error", {"error": f"Fallo al intentar recuperar el estado de la partida: {str(e)}"})
            return

        # Verificar si el movimiento es válido
        try:
            move_obj = chess.Move.from_uci(move_uci)
            if move_obj not in board.legal_moves:
                emit("error", {"error": "Movimiento inválido según las reglas"})
                return

            board.push(move_obj)
            fen_server = board.fen()

        except Exception as e:
            emit("error", {"error": f"Fallo al procesar el movimiento recibido: {str(e)}"})
            return
        
        # Guardar el tiempo restante del jugado
        try:
            cursor.execute("SELECT player1_id, player2_id FROM games WHERE id=%s", (game_id,))
            row = cursor.fetchone()
            if row is None:
                emit("error", {"error": "El partida no existe"})
                return
            p1_id, p2_id = row
            if player_id == p1_id:
                cursor.execute("UPDATE games SET player1_time=%s, player2_time=%s WHERE id=%s", (my_time, opponent_time, game_id))
            else:
                cursor.execute("UPDATE games SET player2_time=%s, player1_time=%s WHERE id=%s", (my_time, opponent_time, game_id))
            conn.commit()

        except Exception as e:
            emit("error", {"error": f"Error durante la sincronización del tiempo: {str(e)}"})
            return

        # Guardar en el sistema un movimiento previamente validado
        try:
            cursor.execute("""
                INSERT INTO moves (game_id, move, move_index, player_id)
                VALUES (%s, %s, %s, %s)
            """, (game_id, move_uci, len(moves), player_id))
            conn.commit()
        except Exception as e:
            emit("error", {"error": "Error durante la inserción de datos en la BD"})
            return
        
        # CheckMate
        if board.is_game_over():
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_db_connection() as conn:
                    cursor = conn.cursor()

                    if board.is_checkmate():
                        loser_sid = request.sid
                        loser_id = None
                        for uid, sid in room_users[game_id].items():
                            if sid == loser_sid:
                                loser_id = uid
                                break
                        winner_id = p1_id if p2_id == loser_id else p2_id
                        cursor.execute("UPDATE games SET winner_id=%s, end_time=%s, status='finished' WHERE id=%s", (winner_id, now, game_id))

                    elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                        cursor.execute("UPDATE games SET winner_id=NULL, end_time=%s, status='finished' WHERE id=%s", (now, game_id))

                    conn.commit()

        emit("opponent_move", {
            "move": move_uci,
            "fen": fen_server,
            "next_turn": 'w' if board.turn else 'b',
            "finished": board.is_game_over(),
            "result": (
                "draw" if board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw()
                else "win" if board.is_checkmate()
                else None
            ),
            "from_sid": request.sid
        }, to=game_id)


    # Comunicación por WebSocket para el envío de mensajes
    @socketio.on('send_message')
    def handle_send_message(data):
        
        import sys
        print("🟨 DEBUG: data:", data, file=sys.stderr, flush=True)
        print("🟨 DEBUG: session content:", dict(session), file=sys.stderr, flush=True)

        game_id = data.get("game_id")
        message = data.get("message")
        user_id = session.get("user_id")

        now = time.time()
        last_sent = message_cooldown.get(user_id, 0)
        
        print("user_id1:", user_id, type(user_id), file=sys.stderr, flush=True)
        print("data:", data)

        if not game_id or not message or not user_id:
            emit("error", {"error": "Formato de mensaje no válido"})
            return

        if now - last_sent < 1:
            emit("error", {"error": "Estás enviando mensajes demasiado rápido. Inténtalo de nuevo en un momento"})
            return

        if len(message) > 256:
            emit("error", {"error": "El mensaje es demasiado largo. Máximo 256 caracteres"})
            return

        if not all([game_id, message, user_id]):
            emit("error", {"error": "Faltan datos en el mensaje"})
            return

        message_cooldown[user_id] = now
        safe_message = html.escape(message)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(" SELECT username FROM users WHERE id=%s", (user_id,))
            username = cursor.fetchone()[0]
            
            cursor.execute("""INSERT INTO messages (game_id, user_id, message) VALUES (%s, %s, %s)""", (game_id, user_id, safe_message))
            conn.commit()

        emit("new_message", {"user": username, "safe_message": message}, to=str(game_id))


    # Unirse Partida
    @socketio.on('join')
    def on_join(data):
        
        game_id = str(data.get("game_id"))
        
        user_id = session.get("user_id")
        if not user_id:
            emit("error", {"error": "Sesión no válida"})
            return
        
        if not user_id:
            emit("error", {"error": "Usuario no iniciado sesión"})
            return

        join_room(game_id)
        
        with room_lock:
            if game_id not in room_users:
                room_users[game_id] = {}

            if user_id in room_users[game_id]:
                old_sid = room_users[game_id][user_id]

                emit("kicked", {"reason": "Intento de ingreso duplicado"}, to=old_sid)
                handle_disconnect(old_sid)

            room_users[game_id][user_id] = request.sid

            if len(room_users[game_id]) == 2:
                emit("both_players_ready", {}, to=game_id)


    # Recibir la señal de rendición del oponente 
    @socketio.on("resign")
    def handle_resign(data):

        game_id = str(data.get("game_id"))
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        loser_id = session.get("user_id")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT player1_id, player2_id FROM games WHERE id=%s", (game_id,))
            players = cursor.fetchone()
            winner_id = players[0] if players[1] == loser_id else players[1]
            cursor.execute("UPDATE games SET winner_id=%s, end_time=%s, status='finished' WHERE id=%s", (winner_id, now, game_id))
            conn.commit()
            
        emit("opponent_resigned", {}, to=game_id, skip_sid=request.sid)


    # Procesar la señal de detección de tiempo límite alcanzado  
    @socketio.on("timeout")
    def handle_timeout(data):
        
        game_id = str(data.get("game_id"))
        loser_id = session.get("user_id")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT player1_id, player2_id FROM games WHERE id=%s", (game_id,))
            players = cursor.fetchone()
            
            winner_id = players[0] if players[1] == loser_id else players[1]
            
            cursor.execute("UPDATE games SET winner_id=%s, end_time=%s, status='finished' WHERE id=%s", (winner_id, now, game_id))
            conn.commit()

        emit("opponent_timeout", {}, to=game_id, skip_sid=request.sid)
        emit("you_lost_by_timeout", {}, to=request.sid)

    
    # Verificar ausencia prolongada del usuario en la sesión
    @socketio.on("heartbeat")
    def handle_heartbeat(data):

        sid = request.sid
        game_id = str(data.get("game_id"))
        last_heartbeat[sid] = (game_id, datetime.utcnow())


    # Manejar la desconexión del cliente vía WebSocket
    @socketio.on('disconnect')
    def handle_disconnect(sid):
        
        sid = request.sid
        user_id = session.get("user_id")

        game_id = None
        for gid, users in room_users.items():
            for uid, s in users.items():
                if s == sid:
                    game_id = gid
                    break
            if game_id:
                break

        if not game_id:
            return

        with room_lock:
            if user_id and user_id in room_users[game_id]:
                room_users[game_id].pop(user_id)
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("SELECT winner_id, end_time FROM games WHERE id=%s", (game_id,))
                row = cursor.fetchone()
                if row and row[0] is not None and row[1] is not None:
                    return
                
                if len(room_users[game_id]) == 1:
                    remaining_uid = next(iter(room_users[game_id].keys()))
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    with get_db_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE games SET winner_id=%s, end_time=%s WHERE id=%s", (remaining_uid, now, game_id))
                        conn.commit()

                emit("opponent_disconnected", {}, to=game_id)

            if not room_users[game_id]:
                room_users.pop(game_id)

    