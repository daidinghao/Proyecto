from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
import sqlite3

history_bp = Blueprint("history", __name__)

# Ruta para mostrar la vista del historia de la partida
@history_bp.route("/historia_view")
def historia_view():
    return render_template("Historia.html")


# API de paginación
@history_bp.route("/historia")
def historia():
    try:
        if "user_id" not in session:
            return jsonify({"error": "No has iniciado sesión"}), 403 
            
        user_id = session.get("user_id")

        try:
            page = int(request.args.get("page", 1))
        except ValueError:
            return jsonify({"error": "Página no válida"}), 400
        
        page = max(1, min(page, 1000))
        limit = 10
        offset = (page - 1) * limit

        with sqlite3.connect("chess.db") as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT g.end_time, g.winner_id, g.player1_id, g.player2_id,
                    u1.username AS player1_name,
                    u2.username AS player2_name,
                    uw.username AS winner_name
                FROM games g
                JOIN users u1 ON g.player1_id = u1.id
                JOIN users u2 ON g.player2_id = u2.id
                LEFT JOIN users uw ON g.winner_id = uw.id
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.end_time IS NOT NULL
                ORDER BY g.end_time DESC
                LIMIT ? OFFSET ?
            """, (user_id, user_id, limit, offset))
            rows = cursor.fetchall()
            
            cursor.execute("""
                    SELECT COUNT(*) FROM games
                    WHERE (player1_id=? OR player2_id=?) AND end_time IS NOT NULL
                """, (user_id, user_id))
            total = cursor.fetchone()[0]    

            partidas = []

            for row in rows:
                fecha, ganador_id, j1_id, j2_id, j1_nombre, j2_nombre, ganador_nombre = row

                ganador_nombre = ganador_nombre or "Desconocido"
                j1_nombre = j1_nombre or "Jugador 1"
                j2_nombre = j2_nombre or "Jugador 2"

                if ganador_id is None:
                    ganador = perdedor = "Empate"
                else:
                    ganador = ganador_nombre or "Desconocido"
                    if ganador_id == j1_id:
                        perdedor = j2_nombre or "Desconocido"
                    else:
                        perdedor = j1_nombre or "Desconocido"

                partidas.append({
                    "Fecha": fecha,
                    "Ganador": ganador,
                    "Perdedor": perdedor
                })
            
        return jsonify({
            "partidas": partidas,
            "page": page,
            "total": total,
            "limit": limit
        })
    
    except Exception as e:
        return jsonify({"error": "Error al obtener los datos", "details": str(e)}), 500
