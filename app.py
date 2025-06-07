from flask import Flask, jsonify
from flask_socketio import SocketIO
from threading import Lock
from routes import register_blueprints
from routes.socket import register_socketio_events, last_heartbeat
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from extensions import limiter, csrf 
from init_db import init_db
import atexit
from db import get_db_connection
import sqlite3
import threading
import webbrowser

app = Flask(__name__)
app.secret_key = 'super_secret'
app.config["SECRET_KEY"] = "tnA_Rs3lKzQ8b12xPB8x2Dm9ZoZrVyYzPGFgR3LhdGPAoken"

socketio = SocketIO(app, async_mode="threading")
room_users = {}
room_lock = Lock()

limiter.init_app(app) 
csrf.init_app(app)  


# Registrar un plano de ruta
register_blueprints(app)

# Registrarse para eventos de socket.io
register_socketio_events(socketio, room_users, room_lock)

if __name__ == "__main__":
    init_db()
    socketio.run(app, host="0.0.0.0", port=10000, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)

# La autorización ha expirado, no hay nadie contra quien jugar
def clear_expired_games():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM games
            WHERE status = 'waiting'
              AND created_at <= datetime('now', '-30 minutes');
        """)
        conn.commit()


# Limpiar jugadores sin conexión
def remove_inactive_users():
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=45)
    inactive = []

    for sid, (game_id, last_time) in list(last_heartbeat.items()):
        if last_time < threshold:
            inactive.append((sid, game_id))

    for sid, game_id in inactive:
        last_heartbeat.pop(sid, None)
        with room_lock:
            if game_id in room_users:

                # Busque user_id y elimínelo
                to_remove = [uid for uid, s in room_users[game_id].items() if s == sid]
                for uid in to_remove:
                    room_users[game_id].pop(uid)

                # La habitación está vacía
                if not room_users[game_id]:  
                    room_users.pop(game_id)


# Haga clic en los comentarios sobre errores varias veces
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"success": False, "message": "La solicitud es demasiado frecuente, inténtelo de nuevo más tarde."}), 429


# Encabezados de seguridad de respuesta estándar (todas las respuestas están protegidas)
@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response


scheduler = BackgroundScheduler()
scheduler.add_job(remove_inactive_users, 'interval', seconds=30)
scheduler.add_job(lambda: clear_expired_games(), 'interval', minutes=10)
scheduler.start()

atexit.register(lambda: scheduler.shutdown())

