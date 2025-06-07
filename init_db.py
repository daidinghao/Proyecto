import sqlite3

# Inicialización de la tabla
def init_db():
    with sqlite3.connect("chess.db") as conn:
        cursor = conn.cursor()

    # Tabla Usuario
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL CHECK (length(username) <= 20),
        password TEXT NOT NULL CHECK (length(password) <= 255),
        email TEXT NOT NULL CHECK (length(email) <= 255),
        register_date TEXT CHECK (length(register_date) <= 20),
        reset_token TEXT CHECK (length(reset_token) <= 100)
    )
    """)

    # Tabla Partida
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player1_id INTEGER NOT NULL,
        player2_id INTEGER,
        player1_time INTEGER DEFAULT 600,
        player2_time INTEGER DEFAULT 600,
        creator_choice TEXT DEFAULT 'w' CHECK (length(creator_choice) <= 1),
        status TEXT DEFAULT 'waiting' CHECK (length(status) <= 20),                     
        winner_id INTEGER,
        end_time TEXT CHECK (length(end_time) <= 20),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,               
        FOREIGN KEY(player1_id) REFERENCES users(id),
        FOREIGN KEY(player2_id) REFERENCES users(id),
        FOREIGN KEY(winner_id) REFERENCES users(id)
    )
    """)

    # Tabla Movimiento
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        move_index INTEGER NOT NULL,
        move TEXT NOT NULL CHECK (length(move) <= 10),
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP CHECK (length(timestamp) <= 20),
        FOREIGN KEY(game_id) REFERENCES games(id),
        FOREIGN KEY(player_id) REFERENCES users(id)
    )
    """)

    # Tabla Chat
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL CHECK (length(message) <= 1000),
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP CHECK (length(timestamp) <= 20),
        FOREIGN KEY(game_id) REFERENCES games(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
