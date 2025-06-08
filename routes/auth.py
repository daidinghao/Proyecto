from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from email.mime.text import MIMEText
from extensions  import limiter
from db import get_db_connection
import sqlite3
import secrets
import re
import smtplib

auth_bp = Blueprint("auth", __name__)

# Página de inicio de sesión
@auth_bp.route("/")
def index():
    return render_template("IniciaSesion.html")


# Procesamiento de inicio de sesión
@auth_bp.route("/IniciaSesion", methods=["POST"])
@limiter.limit("5 per minute") 
def IniciaSesion():
    username = request.form.get("username")
    password = request.form.get("password")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "El nombre de usuario no existe"}), 401

        if not check_password_hash(user[1], password):
            return jsonify({"success": False, "message": "Error contraseña"}), 401

        session["user_id"] = user[0]
        session["username"] = username
        return jsonify({"success": True})


# Registrar
@auth_bp.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        email = request.form.get("email").strip()

        if password != confirm_password:
            return jsonify({"success": False, "message": "Las contraseñas no coinciden"}), 400
        
        if len(password) < 6:
            return jsonify({"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}), 400

        if len(password) > 13:
            return jsonify({"success": False, "message": "La contraseña debe tener al mayor 13 caracteres"}), 400

        if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            return jsonify({"success": False, "message": "La contraseña debe contener letras y números"}), 400

        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
            return jsonify({"success": False, "message": "El formato del correo electrónico no es válido"}), 400

        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Verificar si el nombre de usuario ya existe
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "El nombre de usuario ya existe"}), 400

            # Verificar si el email ya existe
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return jsonify({"success": False, "message": "Este correo electrónico ya está registrado"}), 400

            # Insertar usuario nuevo
            hashed_pw = generate_password_hash(password)
            cursor.execute("""
                INSERT INTO users (username, password, email)
                VALUES (%s, %s, %s)
            """, (username, hashed_pw, email))
            conn.commit()

        return jsonify({"success": True})

    return render_template("Registro.html")


# Redirigir al formulario de restablecimiento de contraseña
@auth_bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        email = request.form.get("email")

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "Este correo electrónico no está registrado"}), 400

        token = secrets.token_urlsafe(32)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET reset_token=%s WHERE id=%s", (token, user[0]))
            conn.commit()

        reset_url = url_for("auth.reset_password_token", token=token, _external=True)

        # Para presentar
        return jsonify({
                "success": True,
                "message": "El enlace de restablecimiento ha sido generado (modo demo)",
                "reset_url": reset_url
        })
  
    return render_template("Recuperar.html")


# Confirmar Link
@auth_bp.route("/reset_password/<token>", methods=["GET"])
def reset_password_token(token):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE reset_token=%s", (token,))
        user = cursor.fetchone()

    if not user:
        return "El enlace es inválido o ya no está disponible", 403

    return render_template("ResetPassword.html", token=token)


# Recuperación de contraseña
@auth_bp.route("/reset_password", methods=["POST"])
def reset_password():
    token = request.form.get("token")
    password = request.form.get("password")
    confirm_password = request.form.get("confirm_password")

    if password != confirm_password:
        return jsonify({"success": False, "message": "Las contraseñas no coinciden"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "message": "La contraseña debe tener al menos 6 caracteres"}), 400

    if len(password) > 13:
        return jsonify({"success": False, "message": "La contraseña debe tener al mayor 13 caracteres"}), 400
    
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return jsonify({"success": False, "message": "La contraseña debe contener letras y números"}), 400

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE reset_token=%s", (token,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"success": False, "message": "El enlace no es válido o ha expirado"}), 403

        hashed_pw = generate_password_hash(password)
        cursor.execute("UPDATE users SET password=%s, reset_token=NULL WHERE id=%s", (hashed_pw, user[0]))
        conn.commit()

    return redirect(url_for("auth.index"))

# Ir a Menu
@auth_bp.route("/menu")
def main():
    if "user_id" not in session:
        return redirect(url_for("auth.index"))

    return render_template("Menu.html")


# Obtener información del usuario autenticado
@auth_bp.route("/perfil")
def perfil():
    if "user_id" not in session:
        return jsonify({"error": "No has iniciado sesión"}), 401

    user_id = session["user_id"]

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username, email, register_date FROM users WHERE id=%s", (user_id,))
        user = cursor.fetchone()

        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE winner_id = %s) AS wins,
                COUNT(*) FILTER (WHERE winner_id IS NULL AND end_time IS NOT NULL) AS draws,
                COUNT(*) FILTER (WHERE (player1_id = %s OR player2_id = %s) AND winner_id IS NOT NULL AND winner_id != %s) AS losses
            FROM games
            WHERE (player1_id = %s OR player2_id = %s) AND end_time IS NOT NULL
        """, (user_id, user_id, user_id, user_id, user_id, user_id))
        stats = cursor.fetchone()

    return jsonify({
        "username": user[0],
        "email": user[1],
        "register_date": user[2],
        "wins": stats[0],
        "draws": stats[1],
        "losses": stats[2]
    })


# Logout
@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.index"))

