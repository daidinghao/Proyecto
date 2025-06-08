import os
import psycopg2
import urllib.parse as urlparse

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        result = urlparse.urlparse(db_url)
        return psycopg2.connect(
            dbname=result.path[1:],
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    else:
        # respaldo para desarrollo local o configuración manual de ENV
        return psycopg2.connect(
            host=os.environ.get("DB_HOST", "localhost"),
            port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ.get("DB_NAME"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD")
        )
