from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from aplicacion.decano_service import DecanoService

decano_bp = Blueprint("decano", __name__)


def _verificar_decano():
    return session.get("rol") == "decano"


# ============================================================
# PANEL PRINCIPAL (Bienvenida)
# ============================================================
@decano_bp.route("/panel")
def panel():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    stats = DecanoService.obtener_estadisticas()

    return render_template(
        "decano/panel.html",
        nombre=session.get("nombre"),
        stats=stats
    )


# ============================================================
# MÓDULO 1: PROFESORES
# ============================================================
@decano_bp.route("/profesores")
def profesores():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    lista = DecanoService.listar_profesores()

    return render_template(
        "decano/profesores.html",
        nombre=session.get("nombre"),
        profesores=lista
    )


@decano_bp.route("/profesores/agregar")
def agregar_profesor():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    simuladores = DecanoService.listar_simuladores()

    return render_template(
        "decano/agregar_profesor.html",
        nombre=session.get("nombre"),
        simuladores=simuladores
    )


@decano_bp.route("/profesores/crear", methods=["POST"])
def crear_profesor():
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    username = request.form.get("username", "").strip()
    nombre_completo = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    activo = request.form.get("activo") == "on"
    bloqueado = request.form.get("bloqueado") == "on"

    simuladores_ids = [int(x) for x in request.form.getlist("simuladores") if x.isdigit()]

    if not username or not nombre_completo:
        flash("Usuario y nombre son obligatorios", "error")
        return redirect(url_for("decano.agregar_profesor"))

    if not simuladores_ids:
        flash("Debe asignar al menos 1 simulador", "error")
        return redirect(url_for("decano.agregar_profesor"))

    resultado = DecanoService.crear_profesor(
        username, None, nombre_completo, email,
        activo, bloqueado, simuladores_ids
    )

    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("decano.agregar_profesor"))

    return render_template(
        "auth/credenciales_temporales.html",
        titulo="Profesor creado",
        subtitulo="Entrega esta contraseña temporal al docente. Deberá cambiarla al ingresar.",
        credenciales=[{
            "usuario": username,
            "nombre": nombre_completo,
            "password": resultado["password_temporal"],
            "detalle": "Profesor",
        }],
        volver_url=url_for("decano.profesores"),
        volver_texto="Volver a profesores",
    )


@decano_bp.route("/profesores/editar")
def editar_profesor_selector():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    lista = DecanoService.listar_profesores()

    return render_template(
        "decano/editar_profesor.html",
        nombre=session.get("nombre"),
        profesores=lista,
        profesor=None,
        simuladores=None
    )


@decano_bp.route("/profesores/editar/<int:usuario_id>")
def editar_profesor_form(usuario_id):
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    profesor = DecanoService.obtener_profesor(usuario_id)
    if not profesor:
        flash("Profesor no encontrado", "error")
        return redirect(url_for("decano.profesores"))

    lista = DecanoService.listar_profesores()
    simuladores = DecanoService.listar_simuladores()

    return render_template(
        "decano/editar_profesor.html",
        nombre=session.get("nombre"),
        profesores=lista,
        profesor=profesor,
        simuladores=simuladores
    )


@decano_bp.route("/profesores/actualizar/<int:usuario_id>", methods=["POST"])
def actualizar_profesor(usuario_id):
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    accion = request.form.get("accion", "guardar")

    if accion == "resetear":
        return redirect(url_for("decano.editar_profesor_form", usuario_id=usuario_id))

    if accion == "eliminar":
        resultado = DecanoService.eliminar_profesor(usuario_id)
        if "error" in resultado:
            flash(resultado["error"], "error")
        else:
            flash("Profesor eliminado", "exito")
        return redirect(url_for("decano.profesores"))

    # Guardar cambios
    nombre_completo = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    activo = request.form.get("activo") == "on"
    bloqueado = request.form.get("bloqueado") == "on"
    nueva_password = request.form.get("nueva_password", "").strip()
    simuladores_ids = [int(x) for x in request.form.getlist("simuladores") if x.isdigit()]

    resultado = DecanoService.actualizar_profesor(
        usuario_id,
        nombre=nombre_completo,
        email=email,
        activo=activo,
        bloqueado=bloqueado,
        nueva_password=nueva_password if nueva_password else None,
        simuladores_ids=simuladores_ids
    )

    if "error" in resultado:
        flash(resultado["error"], "error")
    else:
        flash("Profesor actualizado", "exito")

    return redirect(url_for("decano.editar_profesor_form", usuario_id=usuario_id))


@decano_bp.route("/profesores/eliminar/<int:usuario_id>", methods=["POST"])
def eliminar_profesor(usuario_id):
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    resultado = DecanoService.eliminar_profesor(usuario_id)

    if "error" in resultado:
        flash(resultado["error"], "error")
    else:
        flash("Profesor eliminado", "exito")

    return redirect(url_for("decano.profesores"))


# ============================================================
# MÓDULO 2: PERMISOS ASIGNADOS
# ============================================================
@decano_bp.route("/permisos")
def permisos():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    data = DecanoService.listar_permisos()

    return render_template(
        "decano/permisos.html",
        nombre=session.get("nombre"),
        profesores=data["profesores"],
        simuladores=data["simuladores"]
    )


# ============================================================
# MÓDULO 3: SIMULACIONES
# ============================================================
@decano_bp.route("/simulaciones")
def simulaciones():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    simuladores = DecanoService.listar_simuladores()

    return render_template(
        "decano/simulaciones.html",
        nombre=session.get("nombre"),
        simuladores=simuladores
    )


# ============================================================
# MÓDULO 4: ADMINISTRAR CONTRASEÑAS
# ============================================================
@decano_bp.route("/contrasenas")
def contrasenas():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    usuarios = DecanoService.listar_todos_los_usuarios()

    return render_template(
        "decano/contrasenas.html",
        nombre=session.get("nombre"),
        usuarios=usuarios  # 👈 Enviamos todos los usuarios
    )

@decano_bp.route("/usuarios/<int:usuario_id>/eliminar", methods=["POST"])

def eliminar_usuario(usuario_id):
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    if usuario_id == session.get("usuario_id"):
        flash("No puedes desactivar tu propia cuenta.", "error")
        return redirect(url_for("decano.contrasenas"))

    resultado = DecanoService.eliminar_usuario(usuario_id)
    
    if "error" in resultado:
        flash(resultado["error"], "error")
    else:
        flash("Usuario eliminado (desactivado) correctamente.", "exito")
        
    return redirect(url_for("decano.contrasenas"))

@decano_bp.route("/usuarios/<int:usuario_id>/resetear", methods=["POST"])
def resetear_password_usuario(usuario_id):
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    if usuario_id == session.get("usuario_id"):
        return jsonify({"error": "Usa la opción de cambiar contraseña para tu propia cuenta."}), 400

    resultado = DecanoService.resetear_password_usuario(usuario_id)
    
    if "error" in resultado:
        return jsonify(resultado), 400
        
    return jsonify(resultado) # Devuelve la nueva contraseña temporal


@decano_bp.route("/contrasenas/resetear/<int:usuario_id>", methods=["POST"])
def resetear_password(usuario_id):
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    if usuario_id == session.get("usuario_id"):
        flash("Usa la opción de cambiar contraseña para tu propia cuenta.", "error")
        return redirect(url_for("decano.contrasenas"))

    nueva = request.form.get("nueva_password", "").strip() or None
    resultado = DecanoService.resetear_password_usuario(usuario_id, nueva)

    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("decano.contrasenas"))

    return render_template(
        "auth/credenciales_temporales.html",
        titulo="Contraseña temporal generada",
        subtitulo="Entrega esta clave a la persona correspondiente.",
        credenciales=[{
            "usuario": resultado["username"],
            "nombre": resultado.get("nombre"),
            "password": resultado["nueva_pass"],
            "detalle": "Cambio obligatorio al ingresar",
        }],
        volver_url=url_for("decano.contrasenas"),
        volver_texto="Volver a contraseñas",
    )


# ============================================================
# MÓDULO 5: CONFIGURACIÓN
# ============================================================
@decano_bp.route("/config")
def config():
    if not _verificar_decano():
        return redirect(url_for("auth.index"))

    configuracion = DecanoService.obtener_configuracion()

    return render_template(
        "decano/config.html",
        nombre=session.get("nombre"),
        config=configuracion
    )


@decano_bp.route("/config/guardar", methods=["POST"])
def guardar_config():
    if not _verificar_decano():
        return jsonify({"error": "No autorizado"}), 403

    campos = [
    "nombre_sistema", "idioma", "tema", "anio_maximo_default", "inflacion_default",
    "bolivia_inflacion_anual", "bolivia_inflacion_acumulada", 
    "bolivia_tipo_cambio_usd", "bolivia_crecimiento_pib", 
    "bolivia_tasa_desempleo", "bolivia_fecha_actualizacion"
]
    for campo in campos:
        valor = request.form.get(campo, "").strip()
        if valor:
            DecanoService.actualizar_configuracion(campo, valor)

    flash("Configuración guardada", "exito")
    return redirect(url_for("decano.config"))
