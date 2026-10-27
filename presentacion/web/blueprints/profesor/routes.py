# presentacion/web/blueprints/profesor/routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash, Response
from aplicacion.profesor_service import ProfesorService
from aplicacion.simulacion_service import SimulacionService
from infraestructura.database import get_session
from core.models import Usuario, Equipo, Industria
from werkzeug.security import generate_password_hash

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
    # Muestra el dashboard del profesor (HTML: profesor/panel.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    stats = ProfesorService.obtener_estadisticas(_profesor_id())
    return render_template("profesor/panel.html", nombre=session.get("nombre"), stats=stats)


# ============================================================
# SIMULADORES
# ============================================================
@profesor_bp.route("/simuladores")
def simuladores():
    # Muestra el catálogo de simuladores disponibles (HTML: profesor/simuladores.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    lista = ProfesorService.listar_simuladores()
    return render_template("profesor/simuladores.html", nombre=session.get("nombre"), simuladores=lista)


# ============================================================
# SIMULACIONES (Industrias)
# ============================================================
@profesor_bp.route("/simulaciones")
def simulaciones():
    # Lista las simulaciones creadas por el profesor (HTML: profesor/simulaciones.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    lista = ProfesorService.listar_industrias(_profesor_id())
    return render_template("profesor/simulaciones.html", nombre=session.get("nombre"), industrias=lista)


@profesor_bp.route("/simulaciones/nueva")
def nueva_simulacion():
    # Formulario para crear una nueva simulación (HTML: profesor/nueva_simulacion.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    return render_template("profesor/nueva_simulacion.html", nombre=session.get("nombre"))


@profesor_bp.route("/simulaciones/crear", methods=["POST"])
def crear_simulacion():
    # Procesa el formulario de creación (Conecta con: ProfesorService.crear_industria)
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

    resultado = ProfesorService.crear_industria(_profesor_id(), nombre, num_equipos_int, simulador_codigo)

    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("profesor.nueva_simulacion"))

    flash(f"Simulación '{nombre}' creada con {num_equipos_int} equipos", "exito")
    return redirect(url_for("profesor.detalle_simulacion", industria_id=resultado["industria_id"]))


@profesor_bp.route("/simulaciones/<int:industria_id>")
def detalle_simulacion(industria_id):
    # Muestra el detalle de una simulación (HTML: profesor/simulacion_detalle.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template("profesor/simulacion_detalle.html", nombre=session.get("nombre"), industria=industria)


@profesor_bp.route("/simulaciones/<int:industria_id>/eliminar", methods=["POST"])
def eliminar_simulacion(industria_id):
    # Elimina una simulación y sus datos (Conecta con: ProfesorService.eliminar_industria)
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
    # Habilita/Deshabilita el envío de decisiones (Conecta con: ProfesorService.toggle_permitir_envio)
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.toggle_permitir_envio(industria_id)
    if "error" in resultado:
        return jsonify(resultado), 400

    flash(f"Envío de decisiones {'habilitado' if resultado['permitir_envio'] else 'deshabilitado'}", "exito")
    return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))


# ============================================================
# DECISIONES Y PROCESAR RONDA
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/decisiones")
def decisiones(industria_id):
    # Muestra las decisiones enviadas por los equipos (HTML: profesor/decisiones.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    data = ProfesorService.obtener_decisiones_industria(industria_id)
    if not data:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template("profesor/decisiones.html", nombre=session.get("nombre"), data=data)


@profesor_bp.route("/simulaciones/<int:industria_id>/procesar", methods=["POST"])
def procesar_ronda(industria_id):
    # Ejecuta el motor de simulación para calcular el año (Conecta con: SimulacionService.procesar_ronda)
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


# ============================================================
# RESULTADOS
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/resultados")
def resultados(industria_id):
    # Muestra los resultados generales de la simulación (HTML: profesor/resultados.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    data = ProfesorService.obtener_resultados(industria_id)
    if not data:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template("profesor/resultados.html", nombre=session.get("nombre"), data=data)


# ============================================================
# GESTIÓN DE CONTRASEÑAS Y ALUMNOS
# ============================================================
@profesor_bp.route("/contrasenas")
def contrasenas():
    # Lista los alumnos para gestionarlos (HTML: profesor/contrasenas.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    alumnos = ProfesorService.listar_alumnos_por_profesor(_profesor_id())
    return render_template("profesor/contrasenas.html", nombre=session.get("nombre"), alumnos=alumnos)


@profesor_bp.route("/alumnos/<int:alumno_id>/eliminar", methods=["POST"])
def eliminar_alumno(alumno_id):
    # Desvincula a un alumno de su equipo (Conecta con: ProfesorService.eliminar_alumno)
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.eliminar_alumno(alumno_id)
    
    if "error" in resultado:
        flash(resultado["error"], "error")
    else:
        flash("Alumno desvinculado del equipo correctamente.", "exito")
        
    return redirect(url_for("profesor.contrasenas"))


@profesor_bp.route("/alumnos/<int:alumno_id>/editar", methods=["GET", "POST"])
def editar_alumno(alumno_id):
    # Muestra y procesa el formulario de edición de alumno (HTML: profesor/editar_alumno.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    session_db = get_session()
    try:
        alumno = session_db.query(Usuario).filter_by(id=alumno_id, rol="alumno").first()
        if not alumno:
            flash("Alumno no encontrado", "error")
            return redirect(url_for("profesor.contrasenas"))

        if request.method == "POST":
            nombre = request.form.get("nombre", "").strip()
            email = request.form.get("email", "").strip()
            nueva_pass = request.form.get("password", "").strip()
            equipo_id = request.form.get("equipo_id")
            activo = request.form.get("activo") == "on"

            alumno.nombre = nombre
            alumno.email = email
            alumno.activo = activo
            
            if equipo_id and equipo_id.strip():
                alumno.equipo_id = int(equipo_id)
            else:
                alumno.equipo_id = None

            if nueva_pass:
                alumno.password_hash = generate_password_hash(nueva_pass)

            session_db.commit()
            flash("Alumno actualizado correctamente", "exito")
            return redirect(url_for("profesor.contrasenas"))

        # Traemos los equipos de las industrias de este profesor
        equipos = session_db.query(Equipo, Industria).join(Industria).filter(Industria.profesor_id == _profesor_id()).all()
        lista_equipos = [{"id": eq.id, "nombre": f"Equipo {eq.numero} - {ind.nombre}"} for eq, ind in equipos]

        return render_template("profesor/editar_alumno.html", nombre=session.get("nombre"), alumno=alumno, equipos=lista_equipos)
    finally:
        session_db.close()


@profesor_bp.route("/alumnos/<int:alumno_id>/resetear", methods=["POST"])
def resetear_alumno_password(alumno_id):
    # Resetea la contraseña del alumno a "PASSWORD" (AJAX desde contrasenas.html)
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    session_db = get_session()
    try:
        alumno = session_db.query(Usuario).filter_by(id=alumno_id, rol="alumno").first()
        if not alumno:
            return jsonify({"error": "Alumno no encontrado"}), 404

        alumno.password_hash = generate_password_hash("PASSWORD")
        session_db.commit()
        return jsonify({"ok": True, "username": alumno.username})
    except Exception as e:
        session_db.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        session_db.close()


# ============================================================
# MANUAL, IMPORTAR Y EXPORTAR CSV
# ============================================================
@profesor_bp.route("/manual")
def manual():
    # Muestra el manual de uso para el profesor (HTML: profesor/manual.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    return render_template("profesor/manual.html", nombre=session.get("nombre"))


@profesor_bp.route("/simulaciones/<int:industria_id>/importar")
def importar_alumnos_form(industria_id):
    # Muestra el formulario para cargar un CSV de alumnos (HTML: profesor/importar_alumnos.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    ultimo_import = session.pop("ultimo_import_alumnos", None)
    return render_template("profesor/importar_alumnos.html", nombre=session.get("nombre"), industria=industria, ultimo_import=ultimo_import)


@profesor_bp.route("/simulaciones/<int:industria_id>/importar_csv", methods=["POST"])
def importar_alumnos_csv(industria_id):
    # Procesa el archivo CSV y crea a los alumnos (Conecta con: ProfesorService.importar_alumnos_csv)
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
    session["ultimo_import_alumnos"] = {"creados": resultado["creados"], "errores": resultado["errores"]}

    return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))


@profesor_bp.route("/simulaciones/<int:industria_id>/exportar_csv")
def exportar_resultados_csv(industria_id):
    # Genera y descarga un CSV con los resultados (Conecta con: ProfesorService.exportar_resultados_csv)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    anio = industria["anio_actual"]
    contenido = ProfesorService.exportar_resultados_csv(industria_id, anio)

    if not contenido:
        flash("No hay resultados para exportar", "error")
        return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))

    nombre_archivo = industria["nombre"].replace(" ", "_")
    
    return Response(
        contenido,
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=resultados_{nombre_archivo}_anio_{anio}.csv"}
    )