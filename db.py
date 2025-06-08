import os
import psycopg2
import urllib.parse as urlparse

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise Exception("Variable de entorno DATABASE_URL no establecida")

    result = urlparse.urlparse(db_url)
    return psycopg2.connect(
        dbname=result.path[1:],
        user=result.username,
        password=result.password,
        host=result.hostname,
        port=result.port
    )
