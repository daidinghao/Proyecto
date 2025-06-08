from db import get_db_connection


# Inicialización de la tabla
def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

    # Tabla Usuario
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(20) UNIQUE NOT NULL,
        password VARCHAR(1024) NOT NULL,
        email VARCHAR(255) NOT NULL,
        register_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reset_token VARCHAR(100)
    )
    """)

    # Tabla Partida
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS games (
        id SERIAL PRIMARY KEY,
        player1_id INTEGER NOT NULL,
        player2_id INTEGER,
        player1_time INTEGER DEFAULT 600,
        player2_time INTEGER DEFAULT 600,
        creator_choice VARCHAR(1) DEFAULT 'w',
        status VARCHAR(20) DEFAULT 'waiting',                     
        winner_id INTEGER,
        end_time VARCHAR(20),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,               
        FOREIGN KEY(player1_id) REFERENCES users(id),
        FOREIGN KEY(player2_id) REFERENCES users(id),
        FOREIGN KEY(winner_id) REFERENCES users(id)
    )
    """)

    # Tabla Movimiento
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS moves (
        id SERIAL PRIMARY KEY,
        game_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        move_index INTEGER NOT NULL,
        move VARCHAR(10) NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(game_id) REFERENCES games(id),
        FOREIGN KEY(player_id) REFERENCES users(id)
    )
    """)

    # Tabla Chat
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id SERIAL PRIMARY KEY,
        game_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        timestamp VARCHAR(20) DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(game_id) REFERENCES games(id),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
