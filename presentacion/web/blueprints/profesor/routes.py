# presentacion/web/blueprints/profesor/routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from aplicacion.profesor_service import ProfesorService

from aplicacion.simulacion_service import SimulacionService
from flask import Response

profesor_bp = Blueprint("profesor", __name__)


def _verificar_profesor():
    return session.get("rol") == "profesor"


def _profesor_id():
    return session.get("usuario_id")


# ============================================================
# PANEL PRINCIPAL
# ============================================================
@profesor_bp.route("/panel")
def panel():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    stats = ProfesorService.obtener_estadisticas(_profesor_id())

    return render_template(
        "profesor/panel.html",
        nombre=session.get("nombre"),
        stats=stats
    )


# ============================================================
# SIMULADORES
# ============================================================
@profesor_bp.route("/simuladores")
def simuladores():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    lista = ProfesorService.listar_simuladores()

    return render_template(
        "profesor/simuladores.html",
        nombre=session.get("nombre"),
        simuladores=lista
    )


# ============================================================
# SIMULACIONES (Industrias)
# ============================================================
@profesor_bp.route("/simulaciones")
def simulaciones():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    lista = ProfesorService.listar_industrias(_profesor_id())

    return render_template(
        "profesor/simulaciones.html",
        nombre=session.get("nombre"),
        industrias=lista
    )


@profesor_bp.route("/simulaciones/nueva")
def nueva_simulacion():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    return render_template(
        "profesor/nueva_simulacion.html",
        nombre=session.get("nombre")
    )


@profesor_bp.route("/simulaciones/crear", methods=["POST"])
def crear_simulacion():
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    nombre = request.form.get("nombre", "").strip()
    num_equipos = request.form.get("num_equipos", "5").strip()
    simulador_codigo = request.form.get("simulador", "markestrated").strip()

    if not nombre:
        flash("El nombre de la simulación es obligatorio", "error")
        return redirect(url_for("profesor.nueva_simulacion"))

    try:
        num_equipos_int = int(num_equipos)
        if num_equipos_int < 2 or num_equipos_int > 10:
            raise ValueError()
    except ValueError:
        flash("El número de equipos debe estar entre 2 y 10", "error")
        return redirect(url_for("profesor.nueva_simulacion"))

    resultado = ProfesorService.crear_industria(
        _profesor_id(), nombre, num_equipos_int, simulador_codigo
    )

    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("profesor.nueva_simulacion"))

    flash(f"Simulación '{nombre}' creada con {num_equipos_int} equipos", "exito")
    return redirect(url_for("profesor.detalle_simulacion", industria_id=resultado["industria_id"]))


@profesor_bp.route("/simulaciones/<int:industria_id>")
def detalle_simulacion(industria_id):
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template(
        "profesor/simulacion_detalle.html",
        nombre=session.get("nombre"),
        industria=industria
    )


@profesor_bp.route("/simulaciones/<int:industria_id>/eliminar", methods=["POST"])
def eliminar_simulacion(industria_id):
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.eliminar_industria(industria_id)

    if "error" in resultado:
        flash(resultado["error"], "error")
    else:
        flash("Simulación eliminada", "exito")

    return redirect(url_for("profesor.simulaciones"))


@profesor_bp.route("/simulaciones/<int:industria_id>/toggle_envio", methods=["POST"])
def toggle_envio(industria_id):
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.toggle_permitir_envio(industria_id)
    if "error" in resultado:
        return jsonify(resultado), 400

    flash(f"Envío de decisiones {'habilitado' if resultado['permitir_envio'] else 'deshabilitado'}", "exito")
    return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))


# ============================================================
# DECISIONES
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/decisiones")
def decisiones(industria_id):
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    data = ProfesorService.obtener_decisiones_industria(industria_id)
    if not data:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template(
        "profesor/decisiones.html",
        nombre=session.get("nombre"),
        data=data
    )


# ============================================================
# RESULTADOS
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/resultados")
def resultados(industria_id):
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    data = ProfesorService.obtener_resultados(industria_id)
    if not data:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template(
        "profesor/resultados.html",
        nombre=session.get("nombre"),
        data=data
    )


# ============================================================
# CONTRASEÑAS
# ============================================================
@profesor_bp.route("/contrasenas")
def contrasenas():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    return render_template(
        "profesor/contrasenas.html",
        nombre=session.get("nombre")
    )
    
@profesor_bp.route("/simulaciones/<int:industria_id>/procesar", methods=["POST"])
def procesar_ronda(industria_id):
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = SimulacionService.procesar_ronda(industria_id)

    if "error" in resultado:
        flash(f"Error al procesar: {resultado['error']}", "error")
    else:
        flash(
            f"✅ Ronda {resultado['anio_procesado']} procesada. "
            f"{resultado['total_equipos']} equipos, {resultado['total_marcas']} marcas.",
            "exito"
        )

    return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))

@profesor_bp.route("/manual")
def manual():
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    return render_template(
        "profesor/manual.html",
        nombre=session.get("nombre")
    )

# ============================================================
# IMPORTAR ALUMNOS DESDE CSV
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/importar")
def importar_alumnos_form(industria_id):
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    ultimo_import = session.pop("ultimo_import_alumnos", None)

    return render_template(
        "profesor/importar_alumnos.html",
        nombre=session.get("nombre"),
        industria=industria,
        ultimo_import=ultimo_import
    )

@profesor_bp.route("/simulaciones/<int:industria_id>/importar_csv", methods=["POST"])
def importar_alumnos_csv(industria_id):
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    archivo = request.files.get("archivo_csv")
    if not archivo:
        flash("No se seleccionó ningún archivo", "error")
        return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))

    if not archivo.filename.lower().endswith(".csv"):
        flash("El archivo debe ser .csv", "error")
        return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))

    try:
        contenido = archivo.read().decode("utf-8")
    except UnicodeDecodeError:
        try:
            contenido = archivo.read().decode("latin-1")
        except Exception:
            flash("No se pudo leer el archivo", "error")
            return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))

    resultado = ProfesorService.importar_alumnos_csv(industria_id, contenido)

    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))

    creados = len(resultado["creados"])
    errores = len(resultado["errores"])

    mensaje = f"✅ {creados} alumno(s) creado(s)"
    if errores > 0:
        mensaje += f" | ⚠️ {errores} error(es)"

    flash(mensaje, "exito" if creados > 0 else "error")

    # Guardar detalle en sesión para mostrar
    session["ultimo_import_alumnos"] = {
        "creados": resultado["creados"],
        "errores": resultado["errores"],
    }

    return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))


@profesor_bp.route("/simulaciones/<int:industria_id>/exportar_csv")
def exportar_resultados_csv(industria_id):
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    # ✅ CORREGIDO: acceder al dict correctamente
    anio = industria["anio_actual"]
    contenido = ProfesorService.exportar_resultados_csv(industria_id, anio)

    if not contenido:
        flash("No hay resultados para exportar", "error")
        return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))

    nombre_archivo = industria["nombre"].replace(" ", "_")
    
    return Response(
        contenido,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=resultados_{nombre_archivo}_anio_{anio}.csv"
        }
    )