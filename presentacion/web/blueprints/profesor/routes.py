# presentacion/web/blueprints/profesor/routes.py
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash, Response
from datetime import datetime
from aplicacion.profesor_service import ProfesorService
from aplicacion.simulacion_service import SimulacionService
from aplicacion.proyecto_service import ProyectoService
from infraestructura.database import get_session
from infraestructura.seguridad import hashear_password, validar_password
from core.models import Usuario, Equipo, Industria

profesor_bp = Blueprint("profesor", __name__)


def _verificar_profesor():
    return session.get("rol") == "profesor"


def _profesor_id():
    return session.get("usuario_id")


def _industria_autorizada(industria_id):
    """True solo si la simulación pertenece al profesor en sesión."""
    return ProfesorService.profesor_posee_industria(_profesor_id(), industria_id)


def _alumno_autorizado(alumno_id):
    """True solo si el alumno pertenece a una simulación del profesor."""
    return ProfesorService.profesor_posee_alumno(_profesor_id(), alumno_id)


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

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

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

    if not _industria_autorizada(industria_id):
        return jsonify({"error": "No encontrado"}), 404

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

    if not _industria_autorizada(industria_id):
        return jsonify({"error": "No encontrado"}), 404

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

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

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

    if not _industria_autorizada(industria_id):
        return jsonify({"error": "No encontrado"}), 404

    resultado = SimulacionService.procesar_ronda(industria_id, usuario_id=_profesor_id())

    if "error" in resultado:
        flash(f"Error al procesar: {resultado['error']}", "error")
    else:
        mensaje = (
            f"✅ Ronda {resultado['anio_procesado']} procesada: reporte "
            f"{resultado['siguiente_anio']}. {resultado['total_equipos']} equipos, "
            f"{resultado['total_marcas']} marcas, {resultado['estudios_generados']} estudios."
        )
        if resultado["equipos_sin_decision"]:
            nombres = ", ".join(
                f"Equipo {e['numero']}" for e in resultado["equipos_sin_decision"]
            )
            mensaje += f" Sin decisión efectiva: {nombres} (se usaron valores vigentes)."
        proyectos = resultado.get("proyectos") or {}
        if proyectos.get("evaluados"):
            mensaje += (
                f" I+D: {proyectos.get('aprobados', 0)} aprobado(s) de "
                f"{proyectos['evaluados']} evaluado(s)."
            )
        aplicados = resultado.get("proyectos_aplicados") or {}
        if aplicados.get("marcas_nuevas"):
            mensaje += (
                f" Marcas nuevas lanzadas: "
                f"{len(aplicados['marcas_nuevas'])}."
            )
        if resultado["finalizada"]:
            mensaje += " La simulación quedó finalizada."
        flash(mensaje, "exito")

    return redirect(url_for("profesor.detalle_simulacion", industria_id=industria_id))


@profesor_bp.route("/simulaciones/<int:industria_id>/proyectos")
def proyectos(industria_id):
    # Proyectos de I&D de todos los equipos (HTML: profesor/proyectos.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    industria = ProfesorService.obtener_industria(industria_id)
    if not industria:
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

    return render_template(
        "profesor/proyectos.html",
        nombre=session.get("nombre"),
        industria=industria,
        equipos=ProyectoService.listar_por_industria(industria_id),
    )


# ============================================================
# RESULTADOS
# ============================================================
@profesor_bp.route("/simulaciones/<int:industria_id>/resultados")
def resultados(industria_id):
    # Muestra los resultados generales de la simulación (HTML: profesor/resultados.html)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

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


@profesor_bp.route("/alumnos/resetear-todos", methods=["POST"])
def resetear_todos_alumnos():
    # Genera una clave temporal distinta para cada alumno del profesor.
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.resetear_passwords_alumnos(_profesor_id())
    if "error" in resultado:
        flash(resultado["error"], "error")
        return redirect(url_for("profesor.contrasenas"))

    credenciales = resultado["credenciales"]
    if not credenciales:
        flash("No hay alumnos registrados para resetear.", "error")
        return redirect(url_for("profesor.contrasenas"))

    return render_template(
        "auth/credenciales_temporales.html",
        titulo="Contraseñas temporales generadas",
        subtitulo=f"Se generaron {len(credenciales)} claves nuevas para tus alumnos.",
        credenciales=credenciales,
        volver_url=url_for("profesor.contrasenas"),
        volver_texto="Volver a gestión de contraseñas",
    )


@profesor_bp.route("/alumnos/<int:alumno_id>/eliminar", methods=["POST"])
def eliminar_alumno(alumno_id):
    # Desvincula a un alumno de su equipo (Conecta con: ProfesorService.eliminar_alumno)
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    if not _alumno_autorizado(alumno_id):
        flash("Alumno no encontrado", "error")
        return redirect(url_for("profesor.contrasenas"))

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

    if not _alumno_autorizado(alumno_id):
        flash("Alumno no encontrado", "error")
        return redirect(url_for("profesor.contrasenas"))

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
                try:
                    equipo_id_int = int(equipo_id)
                except ValueError:
                    flash("Equipo no válido", "error")
                    return redirect(url_for("profesor.editar_alumno", alumno_id=alumno_id))
                if not ProfesorService.profesor_posee_equipo(_profesor_id(), equipo_id_int):
                    flash("El equipo seleccionado no pertenece a tus simulaciones", "error")
                    return redirect(url_for("profesor.editar_alumno", alumno_id=alumno_id))
                alumno.equipo_id = equipo_id_int
            else:
                alumno.equipo_id = None

            if nueva_pass:
                ok, mensaje = validar_password(nueva_pass, alumno.username)
                if not ok:
                    flash(mensaje, "error")
                    return redirect(url_for("profesor.editar_alumno", alumno_id=alumno_id))
                alumno.password_hash = hashear_password(nueva_pass)
                alumno.debe_cambiar_password = True
                alumno.password_actualizada = datetime.now()

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
    # Genera una clave temporal; solo para alumnos del profesor en sesión.
    if not _verificar_profesor():
        return jsonify({"error": "No autorizado"}), 403

    resultado = ProfesorService.resetear_password_alumno(_profesor_id(), alumno_id)
    if "error" in resultado:
        estado = 404 if resultado["error"] == "Alumno no encontrado" else 500
        return jsonify(resultado), estado
    return jsonify(resultado)


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

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

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

    if not _industria_autorizada(industria_id):
        return jsonify({"error": "No encontrado"}), 404

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

    if resultado.get("creados"):
        credenciales = [
            {
                "usuario": c["username"],
                "nombre": c["nombre"],
                "password": c["password"],
                "detalle": f"Equipo {c['equipo']}" + (" · Representante" if c["representante"] else ""),
            }
            for c in resultado["creados"]
        ]
        return render_template(
            "auth/credenciales_temporales.html",
            titulo="Alumnos importados",
            subtitulo=f"Se crearon {len(credenciales)} cuentas con contraseña temporal.",
            credenciales=credenciales,
            errores=resultado["errores"],
            volver_url=url_for("profesor.importar_alumnos_form", industria_id=industria_id),
            volver_texto="Volver a importar",
        )

    errores = resultado.get("errores", [])
    detalle = " | ".join(errores[:3]) if errores else "sin filas válidas"
    flash(f"No se creó ningún alumno: {detalle}", "error")
    return redirect(url_for("profesor.importar_alumnos_form", industria_id=industria_id))


@profesor_bp.route("/simulaciones/<int:industria_id>/exportar_csv")
def exportar_resultados_csv(industria_id):
    # Genera y descarga un CSV con los resultados (Conecta con: ProfesorService.exportar_resultados_csv)
    if not _verificar_profesor():
        return redirect(url_for("auth.index"))

    if not _industria_autorizada(industria_id):
        flash("Simulación no encontrada", "error")
        return redirect(url_for("profesor.simulaciones"))

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