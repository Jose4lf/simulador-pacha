from datetime import datetime

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for,
)

from core.models import Usuario
from infraestructura.database import get_session
from infraestructura.seguridad import (
    generar_csrf_token, hashear_password, limpiar_intentos_login, login_bloqueado,
    registrar_fallo_login, segundos_para_desbloqueo, verificar_password,
)

auth_bp = Blueprint(
    "auth",
    __name__,
    template_folder="../../templates/auth"
)

_ROLES_VALIDOS = {"alumno", "profesor", "decano"}


@auth_bp.route("/")
def index():
    if session.get("usuario_id"):
        rol = session.get("rol")
        if rol in _ROLES_VALIDOS:
            return redirect(url_for(f"{rol}.panel"))
    return render_template("auth/login.html", rol_activo="alumno")


@auth_bp.route("/login", methods=["POST"])
def login():
    usuario = request.form.get("usuario", "").strip()
    password = request.form.get("password", "")
    rol = request.form.get("rol", "alumno")
    ip = request.remote_addr or "desconocida"

    if rol not in _ROLES_VALIDOS:
        rol = "alumno"

    if login_bloqueado(usuario, ip):
        minutos = max(1, segundos_para_desbloqueo(usuario, ip) // 60)
        return render_template(
            "auth/login.html",
            error=f"Demasiados intentos fallidos. Espera {minutos} minuto(s).",
            rol_activo=rol,
        ), 429

    db = get_session()
    try:
        user = db.query(Usuario).filter_by(username=usuario).first()

        credenciales_ok = bool(
            user
            and verificar_password(user.password_hash, password)
            and user.rol == rol
            and user.activo
            and not user.bloqueado
        )

        if not credenciales_ok:
            registrar_fallo_login(usuario, ip)
            return render_template(
                "auth/login.html",
                error="Credenciales incorrectas",
                rol_activo=rol,
            )

        datos = {
            "id": user.id,
            "username": user.username,
            "rol": user.rol,
            "nombre": user.nombre,
        }
    finally:
        db.close()

    limpiar_intentos_login(usuario, ip)

    session.clear()
    session.permanent = True
    session["usuario_id"] = datos["id"]
    session["usuario"] = datos["username"]
    session["rol"] = datos["rol"]
    session["nombre"] = datos["nombre"]
    session["csrf_token"] = generar_csrf_token()

    # Ya no se verifica 'debe_cambiar_password', va directo al panel
    return redirect(url_for(f"{datos['rol']}.panel"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.index"))
