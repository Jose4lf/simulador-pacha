from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from aplicacion.alumno_service import AlumnoService
from aplicacion.proyecto_service import ProyectoService

alumno_bp = Blueprint("alumno", __name__)


def _verificar_alumno():
    return session.get("rol") == "alumno"


def _alumno_id():
    return session.get("usuario_id")


def _leer_decisiones(data):
    """Lee la hoja de decisiones del formulario.

    Devuelve (decisiones, error). No aplica reglas de negocio: el servicio
    valida precios, cantidades y canales.
    """
    anio = data["industria"]["anio_actual"]
    canales = data.get("canales", [])
    decisiones = {}

    try:
        for marca in data["marcas"]:
            nombre = marca["nombre"]
            precio = float(request.form.get(f"precio_{nombre}", 0))

            if anio == 0:
                publicidad = marca["publicidad_actual"]
                produccion = marca["produccion_actual"]
                vendedores = dict(marca.get("vendedores") or {})
            else:
                publicidad = float(request.form.get(f"publicidad_{nombre}", 0))
                produccion = float(request.form.get(f"produccion_{nombre}", 0))
                vendedores = {}
                for canal in canales:
                    valor = request.form.get(
                        f"vendedores_{canal['id']}_{nombre}", 0
                    )
                    vendedores[canal["id"]] = int(float(valor or 0))

            decisiones[nombre] = {
                "precio": precio,
                "publicidad": publicidad,
                "produccion": produccion,
                "proyecto_id": request.form.get(f"proyecto_id_{nombre}", ""),
                "objetivo_x": request.form.get(f"objetivo_x_{nombre}", None),
                "objetivo_y": request.form.get(f"objetivo_y_{nombre}", None),
                "vendedores": vendedores,
            }

        # Filas de marcas nuevas respaldadas por un proyecto de I&D aprobado.
        for nuevo in data.get("marcas_nuevas", []):
            proyecto = nuevo["nombre"]
            nombre = (request.form.get(
                f"nueva_marca_{proyecto}", ""
            ) or "").strip().upper()
            if not nombre:
                continue
            precio = float(request.form.get(f"precio_nueva_{proyecto}", 0))
            publicidad = float(request.form.get(
                f"publicidad_nueva_{proyecto}", 0
            ))
            produccion = float(request.form.get(
                f"produccion_nueva_{proyecto}", 0
            ))
            vendedores = {}
            for canal in canales:
                valor = request.form.get(
                    f"vendedores_nueva_{canal['id']}_{proyecto}", 0
                )
                vendedores[canal["id"]] = int(float(valor or 0))
            decisiones[nombre] = {
                "precio": precio,
                "publicidad": publicidad,
                "produccion": produccion,
                "proyecto_id": proyecto,
                "objetivo_x": request.form.get(
                    f"objetivo_x_nueva_{proyecto}", None
                ),
                "objetivo_y": request.form.get(
                    f"objetivo_y_nueva_{proyecto}", None
                ),
                "vendedores": vendedores,
            }
    except (TypeError, ValueError):
        return None, "Hay valores numéricos inválidos en la hoja de decisiones."

    return decisiones, None


@alumno_bp.route("/panel")
def panel():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return render_template("alumno/sin_equipo.html", nombre=session.get("nombre"))

    reportes = AlumnoService.listar_reportes(data["equipo"]["id"])

    # Asegurar que el Año 0 esté siempre disponible como referencia.
    anios_presentes = {r["anio"] for r in reportes}
    if 0 not in anios_presentes:
        reporte_inicial = AlumnoService.obtener_reporte(data["equipo"]["id"], 0)
        if not reporte_inicial:
            reportes.insert(0, {
                "anio": 0,
                "mercado_total": 1300000,
                "contribucion_bruta_total": 0,
                "contribucion_neta_total": 0,
                "presupuesto_proximo_periodo": 10000,
                "marcas": [],
            })

    equipos_industria = AlumnoService.listar_equipos_industria(data["industria"]["id"])
    anios_disponibles = [r["anio"] for r in reportes]

    contribuciones_por_firma = {}
    periodos_set = set()

    for eq in equipos_industria:
        firma_nombre = "Firma " + str(eq["numero"])
        contribuciones_por_firma[firma_nombre] = []

        for anio in range(0, int(data["industria"]["anio_actual"]) + 1):
            rep = AlumnoService.obtener_reporte(eq["id"], anio)
            valor = 0.0
            if rep:
                try:
                    valor = float(rep.get("contribucion_neta_total") or 0)
                except (ValueError, TypeError):
                    valor = 0.0
            contribuciones_por_firma[firma_nombre].append(valor)
            periodos_set.add(anio)

    periodos = sorted(periodos_set) if periodos_set else [0]

    participantes = AlumnoService.obtener_participantes(
        data["industria"]["id"], data["equipo"]["id"]
    )

    return render_template(
        "alumno/panel.html",
        nombre=session.get("nombre"),
        data=data,
        reportes=reportes,
        equipos_industria=equipos_industria,
        anios_disponibles=anios_disponibles,
        contribuciones_por_firma=contribuciones_por_firma,
        periodos=periodos,
        participantes=participantes,
    )


@alumno_bp.route("/reporte/<int:anio>")
def reporte(anio):
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    if anio < 0 or anio > data["industria"]["anio_actual"]:
        flash("Reporte no disponible", "error")
        return redirect(url_for("alumno.panel"))

    reporte_obj = AlumnoService.obtener_reporte(data["equipo"]["id"], anio)
    if not reporte_obj:
        flash("Reporte no disponible", "error")
        return redirect(url_for("alumno.panel"))

    return render_template(
        "alumno/reporte.html",
        nombre=session.get("nombre"),
        data=data,
        reporte=reporte_obj,
        anio=anio,
    )


@alumno_bp.route("/decisiones")
def decisiones():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    if not data["industria"]["permitir_envio"]:
        flash("El envío está deshabilitado", "error")
        return redirect(url_for("alumno.panel"))

    if data["industria"]["estado"] == "finalizada":
        flash("La simulación está finalizada", "error")
        return redirect(url_for("alumno.panel"))

    if data["equipo"]["ya_decidio"]:
        flash("Ya enviaste tus decisiones este año", "info")
        return redirect(url_for("alumno.panel"))

    return render_template(
        "alumno/decisiones.html",
        nombre=session.get("nombre"),
        data=data,
        canales=data["canales"],
        estudios_disponibles=data["estudios"],
        estudios_comprados=data["estudios_comprados"],
    )


def _guardar(estado):
    if not _verificar_alumno():
        return jsonify({"error": "No autorizado"}), 403

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return jsonify({"error": "Sin equipo"}), 400

    if not data["industria"]["permitir_envio"]:
        flash("El envío está deshabilitado", "error")
        return redirect(url_for("alumno.panel"))

    anio = data["industria"]["anio_actual"]
    decisiones, error = _leer_decisiones(data)
    if error:
        flash(error, "error")
        return redirect(url_for("alumno.decisiones"))

    estudios_ids = request.form.getlist("estudios")

    resultado = AlumnoService.guardar_decision(
        data["equipo"]["id"],
        anio,
        decisiones,
        canales_ids=[c["id"] for c in data["canales"]],
        estudios_ids=estudios_ids,
        estado=estado,
        usuario_id=_alumno_id(),
    )

    if "error" in resultado:
        flash(f"Error: {resultado['error']}", "error")
        return redirect(url_for("alumno.decisiones"))

    if estado == "borrador":
        flash(f"Borrador del año {anio} guardado", "info")
    else:
        flash(f"Decisiones del año {anio} enviadas", "exito")
    return redirect(url_for("alumno.panel"))


@alumno_bp.route("/decisiones/guardar", methods=["POST"])
def guardar_borrador():
    return _guardar("borrador")


@alumno_bp.route("/decisiones/enviar", methods=["POST"])
def enviar_decision():
    return _guardar("enviada")


@alumno_bp.route("/estudios")
def estudios():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    anio = request.args.get("anio", type=int)
    estudios_data = AlumnoService.listar_estudios_equipo(data["equipo"]["id"], anio)

    return render_template(
        "alumno/estudios.html",
        nombre=session.get("nombre"),
        data=data,
        estudios_data=estudios_data,
        anio=estudios_data["anio"],
    )


@alumno_bp.route("/manual")
def manual():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    return render_template("alumno/manual.html", nombre=session.get("nombre"))


# ============================================================
# PROYECTOS DE I&D
# ============================================================
@alumno_bp.route("/proyectos")
def proyectos():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    contexto = ProyectoService.contexto_equipo(data["equipo"]["id"])
    if not contexto:
        flash("No se pudo cargar el centro de I&D", "error")
        return redirect(url_for("alumno.panel"))

    return render_template(
        "alumno/proyectos.html",
        nombre=session.get("nombre"),
        data=data,
        proyectos=contexto,
    )


@alumno_bp.route("/proyectos/crear", methods=["POST"])
def crear_proyecto():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    if not data["industria"]["permitir_envio"]:
        flash("El envío está deshabilitado", "error")
        return redirect(url_for("alumno.proyectos"))
    if data["industria"]["estado"] == "finalizada":
        flash("La simulación está finalizada", "error")
        return redirect(url_for("alumno.panel"))

    atributos = [
        request.form.get(f"atributo_{numero}", "")
        for numero in range(1, 7)
    ]
    marca_id = request.form.get("marca_id", "").strip()
    datos = {
        "nombre": request.form.get("nombre", ""),
        "marca_id": int(marca_id) if marca_id.isdigit() else None,
        "marca_nueva": request.form.get("marca_nueva", ""),
        "presupuesto": request.form.get("presupuesto", ""),
        "atributos": atributos,
    }

    resultado = ProyectoService.crear_proyecto(
        data["equipo"]["id"], data["industria"]["anio_actual"],
        datos, usuario_id=_alumno_id(),
    )
    if "error" in resultado:
        flash(f"Error: {resultado['error']}", "error")
    else:
        estimacion = resultado["estimacion"]
        flash(
            f"Proyecto {resultado['nombre']} registrado. Presupuesto normal: "
            f"{estimacion['presupuesto_normal']:,.2f} miles de Bs; "
            f"probabilidad estimada: {estimacion['probabilidad'] * 100:.0f}%. "
            "El resultado se conocerá al procesar la ronda.",
            "exito",
        )
    return redirect(url_for("alumno.proyectos"))


@alumno_bp.route("/proyectos/<int:proyecto_id>/cancelar", methods=["POST"])
def cancelar_proyecto(proyecto_id):
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    resultado = ProyectoService.cancelar_proyecto(
        data["equipo"]["id"], proyecto_id, usuario_id=_alumno_id()
    )
    if "error" in resultado:
        flash(f"Error: {resultado['error']}", "error")
    else:
        flash("Proyecto cancelado", "info")
    return redirect(url_for("alumno.proyectos"))
