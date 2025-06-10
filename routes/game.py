from flask import Blueprint, render_template, request, redirect, jsonify, url_for, session
# from routes.socket import room_users, room_lock
from flask import current_app
from db import get_db_connection
import sqlite3
import datetime
import chess

game_bp = Blueprint("game", __name__)

def get_username_by_id(user_id):
    if not user_id:
        return "Invitado"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
        result = cursor.fetchone()
        return result[0] if result else "Usuario desconocido"


# Vista del tabla
@game_bp.route("/partida/<int:game_id>")
def partida(game_id):
    if "user_id" not in session:
        return redirect(url_for("auth.index"))
    
    user_id = session["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT player1_id, player2_id, creator_choice, status FROM games WHERE id=%s", (game_id,))
        game = cursor.fetchone()

        if not game:
            return "La partida no existe"

        player1_id, player2_id, creator_choice, status = game

        if status == 'finished':
            return "La partida ha terminado"

        if user_id == player1_id:
            my_color = creator_choice
        elif user_id == player2_id:
            my_color = 'b' if creator_choice == 'w' else 'w'
        else:
            return "No eres un jugador de esta partida"

    return render_template("Partida.html", game_id=game_id, my_color=my_color)


# Crear Partida
@game_bp.route("/crear_partida")
def crear_partida():
    player1_id = session.get("user_id")
    color = request.args.get("color", "w")  

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""INSERT INTO games (player1_id, player2_id, winner_id, end_time, creator_choice, status) VALUES (%s, NULL, NULL, NULL, %s, 'waiting') RETURNING id""", (player1_id, color))
        game_id = cursor.fetchone()[0]
        conn.commit()

    return redirect(url_for("game.partida", game_id=game_id))   


# Mostrar la lista de partidas en espera
@game_bp.route("/waiting_games")
def waiting_games():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    offset = (page - 1) * limit


    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(""" SELECT g.id, u.username, g.creator_choice FROM games g JOIN users u ON g.player1_id = u.id 
                       WHERE g.status = 'waiting' AND g.player2_id IS NULL ORDER BY g.id DESC LIMIT %s OFFSET %s""", (limit, offset))
        games = cursor.fetchall()

        cursor.execute("""SELECT COUNT(*) FROM games WHERE status = 'waiting' AND player2_id IS NULL""")
        total = cursor.fetchone()[0]


    return jsonify({
        "games": [
            {"id": g[0], "creator_name": g[1], "choice": g[2]}
            for g in games
        ],
        "page": page,
        "limit": limit,
        "total": total
    })


# Unirse Partida
@game_bp.route("/join_game/<int:game_id>")
def join_game(game_id):
    if "user_id" not in session:
        return redirect(url_for("auth.index"))

    user_id = session.get("user_id")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""UPDATE games SET player2_id=%s, status='playing' WHERE id=%s AND player2_id IS NULL""", (user_id, game_id))
        conn.commit()

    return redirect(url_for("game.partida", game_id=game_id))   


# Sincronizar el estado de la partida tras una recarga
@game_bp.route("/game_state/<int:game_id>")
def get_game_state(game_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT move FROM moves WHERE game_id=%s ORDER BY move_index ASC", (game_id,))
        moves = [row[0] for row in cursor.fetchall()]

        cursor.execute("""
            SELECT player1_id, player2_id, player1_time, player2_time
            FROM games WHERE id=%s
        """, (game_id,))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "La partida no existe"}), 404

        p1_id, p2_id, p1_timep, p2_timep = row
        p1_time = 600
        p2_time = 600

    board = chess.Board()
    
    for move in moves:
        board.push_uci(move)
    
    current_turn = 'w' if board.turn else 'b'

    fen = board.fen()
    return jsonify({
        "moves": moves,
        "player1_time": p1_time,
        "player2_time": p2_time,
        "current_turn": current_turn,
        "fen": fen
    })


# Modo espectador

# Mostrar la lista de partidas disponibles para espectar

@game_bp.route("/watch_list")
def watch_list():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    offset = (page - 1) * limit

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""SELECT g.id, u1.username, u2.username 
                        FROM games g JOIN users u1 ON g.player1_id = u1.id JOIN users u2 ON g.player2_id = u2.id
                        WHERE g.status = 'playing' AND g.winner_id IS NULL AND g.end_time IS NULL
                        ORDER BY g.id DESC LIMIT %s OFFSET %s""", (limit, offset))
        games = cursor.fetchall()

        cursor.execute("""
            SELECT COUNT(*) FROM games
            WHERE status = 'playing'
        """)
        total = cursor.fetchone()[0]
        
    return jsonify({
        "games": [
            {"id": g[0], "player1": g[1], "player2": g[2]}
            for g in games
        ],
        "page": page,
        "limit": limit,
        "total": total
    })


# Ir a la vista de espectador.
@game_bp.route("/watch/<int:game_id>")
def watch_game(game_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""SELECT player1_id, player2_id, winner_id FROM games WHERE id=%s""", (game_id,))
        game = cursor.fetchone()

        player1_id, player2_id, winner_id = game

        if not game:
            return "La partida no existe"

        if winner_id:
            return redirect(url_for("menu"))

        username = get_username_by_id(session.get("user_id"))

    return render_template("Partida.html",
                           game_id=game_id,
                           my_color=None,
                           username=username,
                           spectator=True)


# Cargar mensajes del chat
@game_bp.route("/chat_history/<int:game_id>")
def chat_history(game_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.username, m.message
            FROM messages m
            JOIN users u ON m.user_id = u.id
            WHERE m.game_id=%s
            ORDER BY m.timestamp ASC
        """, (game_id,))
        records = cursor.fetchall()

    return jsonify([
        {"user": r[0], "message": r[1]} for r in records
    ])





