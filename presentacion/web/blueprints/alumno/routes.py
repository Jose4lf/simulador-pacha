from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, flash
from aplicacion.alumno_service import AlumnoService

alumno_bp = Blueprint("alumno", __name__)


def _verificar_alumno():
    return session.get("rol") == "alumno"


def _alumno_id():
    return session.get("usuario_id")


@alumno_bp.route("/panel")
def panel():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return render_template("alumno/sin_equipo.html", nombre=session.get("nombre"))

    reportes = AlumnoService.listar_reportes(data["equipo"]["id"])

    # Asegurar que el Año 0 esté siempre disponible
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
                v = rep.get("contribucion_neta_total", 0)
                try:
                    valor = float(v) if v is not None else 0.0
                except (ValueError, TypeError):
                    valor = 0.0
            contribuciones_por_firma[firma_nombre].append(valor)
            periodos_set.add(anio)

    periodos = sorted(periodos_set) if periodos_set else [0]

    # ✅ NUEVO: calcular participantes
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
        participantes=participantes,   # ✅ NUEVO
    )


@alumno_bp.route("/reporte/<int:anio>")
def reporte(anio):
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
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

    if data["equipo"]["ya_decidio"]:
        flash("Ya enviaste tus decisiones este año", "info")
        return redirect(url_for("alumno.panel"))

    return render_template(
        "alumno/decisiones.html",
        nombre=session.get("nombre"),
        data=data,
    )


@alumno_bp.route("/decisiones/enviar", methods=["POST"])
def enviar_decision():
    if not _verificar_alumno():
        return jsonify({"error": "No autorizado"}), 403

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return jsonify({"error": "Sin equipo"}), 400

    anio = data["industria"]["anio_actual"]

    decisiones = {}
    for marca in data["marcas"]:
        nombre_marca = marca["nombre"]
        try:
            precio = float(request.form.get(f"precio_{nombre_marca}", 0))
            publicidad = float(request.form.get(f"publicidad_{nombre_marca}", 0))
            produccion = float(request.form.get(f"produccion_{nombre_marca}", 0))
        except ValueError:
            flash(f"Valores invalidos en {nombre_marca}", "error")
            return redirect(url_for("alumno.decisiones"))

        if anio == 0:
            publicidad = marca["publicidad_actual"]
            produccion = marca["produccion_actual"]

        decisiones[nombre_marca] = {
            "precio": precio,
            "publicidad": publicidad,
            "produccion": produccion,
            "proyecto_id": request.form.get(f"proyecto_id_{nombre_marca}", ""),
        }

    resultado = AlumnoService.guardar_decision(data["equipo"]["id"], anio, decisiones)

    if "error" in resultado:
        flash(f"Error: {resultado['error']}", "error")
        return redirect(url_for("alumno.decisiones"))

    flash(f"Decisiones del Ano {anio} enviadas", "exito")
    return redirect(url_for("alumno.panel"))


@alumno_bp.route("/estudios")
def estudios():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    data = AlumnoService.obtener_equipo_del_alumno(_alumno_id())
    if not data:
        return redirect(url_for("alumno.panel"))

    estudios_lista = AlumnoService.listar_estudios_disponibles()

    return render_template(
        "alumno/estudios.html",
        nombre=session.get("nombre"),
        data=data,
        estudios=estudios_lista,
    )


@alumno_bp.route("/manual")
def manual():
    if not _verificar_alumno():
        return redirect(url_for("auth.index"))

    return render_template("alumno/manual.html", nombre=session.get("nombre"))
