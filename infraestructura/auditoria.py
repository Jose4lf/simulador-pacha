"""
Auditoría de integridad de PACHA — solo lectura.

No crea, modifica ni elimina registros. Devuelve una lista de hallazgos
clasificados como OK, WARN o FAIL para que puedan mostrarse por consola
o reutilizarse en pruebas.
"""
from dataclasses import asdict, dataclass

from sqlalchemy import inspect

from core.models import (
    Base, Canal, CompraEstudio, Decision, DecisionMarca, Equipo,
    Industria, LogActividad, Marca, Reporte, ReporteMarca,
    ReporteMarcaCanal, ReporteMarcaSegmento, Segmento, Usuario,
)
from infraestructura.database import get_db_info, get_session
from infraestructura.seguridad import es_hash


@dataclass
class Hallazgo:
    nivel: str   # OK | WARN | FAIL
    codigo: str
    mensaje: str


def _agregar(hallazgos, nivel, codigo, mensaje):
    hallazgos.append(Hallazgo(nivel=nivel, codigo=codigo, mensaje=mensaje))


def _tabla_existe(session, nombre):
    return nombre in inspect(session.get_bind()).get_table_names()


def _verificar_esquema(session, hallazgos):
    reales = set(inspect(session.get_bind()).get_table_names())
    modelos = set(Base.metadata.tables)

    faltan = sorted(modelos - reales)
    sobran = sorted(reales - modelos - {"alembic_version"})
    if faltan:
        _agregar(hallazgos, "FAIL", "ESQUEMA_TABLAS_FALTAN",
                 f"Tablas del modelo ausentes en la BD: {', '.join(faltan)}")
    if sobran:
        _agregar(hallazgos, "WARN", "ESQUEMA_TABLAS_SOBRAN",
                 f"Tablas en la BD sin modelo: {', '.join(sobran)}")
    if not faltan and not sobran:
        _agregar(hallazgos, "OK", "ESQUEMA_TABLAS",
                 f"Las {len(reales - {'alembic_version'})} tablas coinciden con los modelos.")

    columnas_faltantes = []
    for tabla in sorted(modelos & reales):
        modelo_cols = {c.name for c in Base.metadata.tables[tabla].columns}
        bd_cols = {c["name"] for c in inspect(session.get_bind()).get_columns(tabla)}
        if modelo_cols - bd_cols:
            columnas_faltantes.append(f"{tabla}: {sorted(modelo_cols - bd_cols)}")
    if columnas_faltantes:
        _agregar(hallazgos, "FAIL", "ESQUEMA_COLUMNAS_FALTAN",
                 "Columnas del modelo ausentes en la BD: " + "; ".join(columnas_faltantes))
    else:
        _agregar(hallazgos, "OK", "ESQUEMA_COLUMNAS",
                 "Todas las columnas del modelo existen en la BD.")


def _verificar_huerfanos(session, hallazgos):
    pares = [
        ("usuarios.equipo_id -> equipos", Usuario, Usuario.equipo_id, Equipo),
        ("equipos.industria_id -> industrias", Equipo, Equipo.industria_id, Industria),
        ("marcas.equipo_id -> equipos", Marca, Marca.equipo_id, Equipo),
        ("segmentos.industria_id -> industrias", Segmento, Segmento.industria_id, Industria),
        ("canales.industria_id -> industrias", Canal, Canal.industria_id, Industria),
        ("reportes.equipo_id -> equipos", Reporte, Reporte.equipo_id, Equipo),
        ("reporte_marca.reporte_id -> reportes", ReporteMarca, ReporteMarca.reporte_id, Reporte),
        ("reporte_marca_canal.reporte_marca_id", ReporteMarcaCanal, ReporteMarcaCanal.reporte_marca_id, ReporteMarca),
        ("reporte_marca_segmento.reporte_marca_id", ReporteMarcaSegmento, ReporteMarcaSegmento.reporte_marca_id, ReporteMarca),
        ("decisiones.equipo_id -> equipos", Decision, Decision.equipo_id, Equipo),
        ("decision_marca.decision_id -> decisiones", DecisionMarca, DecisionMarca.decision_id, Decision),
        ("compras_estudios.equipo_id -> equipos", CompraEstudio, CompraEstudio.equipo_id, Equipo),
    ]

    for etiqueta, hijo, fk, padre in pares:
        try:
            cantidad = (
                session.query(hijo)
                .outerjoin(padre, fk == padre.id)
                .filter(fk.isnot(None), padre.id.is_(None))
                .count()
            )
        except Exception as exc:
            _agregar(hallazgos, "WARN", "HUERFANOS_ERROR",
                     f"No se pudo verificar {etiqueta}: {exc}")
            continue

        if cantidad:
            _agregar(hallazgos, "FAIL", "HUERFANOS",
                     f"{cantidad} registro(s) huérfano(s) en {etiqueta}.")
        else:
            _agregar(hallazgos, "OK", "HUERFANOS",
                     f"Sin huérfanos en {etiqueta}.")

    no_profesor = (
        session.query(Industria)
        .join(Usuario, Industria.profesor_id == Usuario.id)
        .filter(Usuario.rol != "profesor")
        .count()
    )
    if no_profesor:
        _agregar(hallazgos, "WARN", "INDUSTRIA_PROFESOR_ROL",
                 f"{no_profesor} industria(s) asignada(s) a un usuario que no es profesor.")


def _verificar_catalogos(session, hallazgos):
    industrias = session.query(Industria).order_by(Industria.id).all()
    if not industrias:
        _agregar(hallazgos, "WARN", "SIN_INDUSTRIAS",
                 "No hay industrias registradas.")
        return

    for ind in industrias:
        etiqueta = f"industria {ind.id} ({ind.nombre})"
        segmentos = session.query(Segmento).filter_by(industria_id=ind.id).all()
        canales = session.query(Canal).filter_by(industria_id=ind.id).all()
        equipos = session.query(Equipo).filter_by(industria_id=ind.id).order_by(Equipo.numero).all()

        if len(segmentos) != 5:
            _agregar(hallazgos, "WARN", "SEGMENTOS",
                     f"{etiqueta}: se esperaban 5 segmentos y hay {len(segmentos)}.")
        suma_pesos = sum(float(s.peso or 0) for s in segmentos)
        if abs(suma_pesos - 1.0) > 0.001:
            _agregar(hallazgos, "FAIL", "PESOS_SEGMENTOS",
                     f"{etiqueta}: los pesos suman {suma_pesos:.4f}, deberían sumar 1.0.")

        if len(canales) != 3:
            _agregar(hallazgos, "WARN", "CANALES",
                     f"{etiqueta}: se esperaban 3 canales y hay {len(canales)}.")

        if not equipos:
            _agregar(hallazgos, "FAIL", "SIN_EQUIPOS",
                     f"{etiqueta}: no tiene equipos.")
            continue

        if ind.anio_actual is None or ind.anio_maximo is None or not (0 <= ind.anio_actual <= ind.anio_maximo):
            _agregar(hallazgos, "FAIL", "ANIO_INVALIDO",
                     f"{etiqueta}: año actual {ind.anio_actual} fuera de rango (máximo {ind.anio_maximo}).")
        if ind.anio_maximo != 10:
            _agregar(hallazgos, "WARN", "ANIO_MAXIMO",
                     f"{etiqueta}: año máximo {ind.anio_maximo}, el escenario objetivo es 10.")

        for eq in equipos:
            marcas = session.query(Marca).filter_by(equipo_id=eq.id, activa=True).count()
            if marcas != 2:
                _agregar(hallazgos, "WARN", "MARCAS_POR_EQUIPO",
                         f"{etiqueta}, equipo {eq.numero}: {marcas} marca(s) activa(s); el objetivo es 2.")


def _verificar_reportes(session, hallazgos):
    equipos = session.query(Equipo).all()
    for eq in equipos:
        rep0 = session.query(Reporte).filter_by(equipo_id=eq.id, anio=0).first()
        if not rep0:
            _agregar(hallazgos, "WARN", "REPORTE_ANIO0",
                     f"Equipo {eq.numero} (id {eq.id}) no tiene reporte de año 0.")

    reportes = session.query(Reporte).all()
    if not reportes:
        _agregar(hallazgos, "WARN", "SIN_REPORTES", "No hay reportes registrados.")
        return

    for rep in reportes:
        if not rep.marcas:
            _agregar(hallazgos, "WARN", "REPORTE_SIN_MARCAS",
                     f"Reporte {rep.id} (equipo {rep.equipo_id}, año {rep.anio}) no tiene marcas.")

        for rm in rep.marcas:
            etiqueta = f"reporte {rep.id} / marca {rm.marca_nombre}"
            if float(rm.produccion or 0) < -0.01:
                _agregar(hallazgos, "FAIL", "PRODUCCION_NEGATIVA", f"{etiqueta}: producción negativa.")
            if float(rm.unidades_vendidas or 0) < -0.01:
                _agregar(hallazgos, "FAIL", "VENTAS_NEGATIVAS", f"{etiqueta}: ventas negativas.")
            if float(rm.inventario or 0) < -0.5:
                _agregar(hallazgos, "FAIL", "INVENTARIO_NEGATIVO", f"{etiqueta}: inventario negativo.")
            if float(rm.unidades_vendidas or 0) > float(rm.produccion or 0) + 0.5:
                _agregar(hallazgos, "FAIL", "VENTAS_MAYOR_PRODUCCION",
                         f"{etiqueta}: ventas {rm.unidades_vendidas} > producción {rm.produccion}.")
            if float(rm.precio_final or 0) < 0:
                _agregar(hallazgos, "FAIL", "PRECIO_NEGATIVO", f"{etiqueta}: precio negativo.")

            ingresos = float(rm.ingresos or 0)
            esperado = float(rm.precio_final or 0) * float(rm.unidades_vendidas or 0)
            tolerancia = max(1.0, abs(esperado) * 0.01)
            if abs(ingresos - esperado) > tolerancia:
                _agregar(hallazgos, "WARN", "INGRESOS_INCOHERENTES",
                         f"{etiqueta}: ingresos {ingresos:.2f} != precio × unidades ({esperado:.2f}).")

            contribucion = float(rm.contribucion_bruta_marketing or 0)
            costo_fuerza_ventas = sum(
                float(c.vendedores or 0) for c in rm.canales
            ) * 30.6
            esperada = (ingresos
                        - float(rm.costo_productos_vendidos or 0)
                        - float(rm.costo_inventario or 0)
                        - float(rm.publicidad or 0)
                        - costo_fuerza_ventas)
            tolerancia_c = max(1.0, abs(esperada) * 0.01)
            if abs(contribucion - esperada) > tolerancia_c:
                _agregar(hallazgos, "WARN", "CONTRIBUCION_INCOHERENTE",
                         f"{etiqueta}: contribución {contribucion:.2f} != ingresos - costos - publicidad - fuerza de ventas ({esperada:.2f}).")

            canales = session.query(ReporteMarcaCanal).filter_by(reporte_marca_id=rm.id).all()
            if canales:
                ventas_canal = sum(float(c.ventas_unidades or 0) for c in canales)
                if abs(ventas_canal - float(rm.unidades_vendidas or 0)) > max(1.0, abs(float(rm.unidades_vendidas or 0)) * 0.01):
                    _agregar(hallazgos, "WARN", "VENTAS_CANAL",
                             f"{etiqueta}: ventas por canal {ventas_canal:.0f} != ventas totales {rm.unidades_vendidas:.0f}.")

    # Participación por industria y año (se almacena en porcentaje)
    industrias = session.query(Industria).all()
    for ind in industrias:
        anios = {rep.anio for rep in reportes if rep.equipo.industria_id == ind.id}
        for anio in sorted(anios):
            porciones = [
                float(rm.porcion_mercado or 0)
                for rep in reportes
                if rep.anio == anio and rep.equipo.industria_id == ind.id
                for rm in rep.marcas
            ]
            if porciones and abs(sum(porciones) - 100.0) > 1.0:
                _agregar(hallazgos, "WARN", "PARTICIPACION",
                         f"Industria {ind.nombre}, año {anio}: la participación suma {sum(porciones):.2f}% (esperado ~100%).")

    segmentos = session.query(ReporteMarcaSegmento).count()
    if segmentos == 0:
        _agregar(hallazgos, "WARN", "SIN_REPORTES_SEGMENTO",
                 "No hay reportes por segmento (se crean al procesar una ronda).")


def _verificar_decisiones(session, hallazgos):
    decisiones = session.query(Decision).all()
    if not decisiones:
        _agregar(hallazgos, "WARN", "SIN_DECISIONES",
                 "No hay decisiones registradas (el flujo aún no se ha ejercitado).")
        return

    for dec in decisiones:
        marcas = session.query(DecisionMarca).filter_by(decision_id=dec.id).all()
        if not marcas:
            _agregar(hallazgos, "WARN", "DECISION_SIN_MARCAS",
                     f"Decisión {dec.id} (equipo {dec.equipo_id}, año {dec.anio}) no tiene marcas.")
        for dm in marcas:
            if float(dm.precio_venta or 0) < 0:
                _agregar(hallazgos, "FAIL", "DECISION_PRECIO_NEGATIVO",
                         f"Decisión {dec.id}, marca {dm.marca_nombre}: precio negativo.")
            if float(dm.produccion or 0) < 0:
                _agregar(hallazgos, "FAIL", "DECISION_PRODUCCION_NEGATIVA",
                         f"Decisión {dec.id}, marca {dm.marca_nombre}: producción negativa.")
            if float(dm.presupuesto_publicitario or 0) < 0:
                _agregar(hallazgos, "FAIL", "DECISION_PUBLICIDAD_NEGATIVA",
                         f"Decisión {dec.id}, marca {dm.marca_nombre}: publicidad negativa.")


def _verificar_compras_y_logs(session, hallazgos):
    compras = session.query(CompraEstudio).count()
    if compras == 0:
        _agregar(hallazgos, "WARN", "SIN_COMPRAS_ESTUDIOS",
                 "No hay compras de estudios (se registran al enviar una decisión).")

    logs = session.query(LogActividad).count()
    if logs == 0:
        _agregar(hallazgos, "WARN", "SIN_LOGS",
                 "No hay registros en logs_actividad; la trazabilidad aún no se usa.")


def _verificar_seguridad(session, hallazgos):
    usuarios = session.query(Usuario).all()

    sin_hash = [u.username for u in usuarios if not es_hash(u.password_hash)]
    if sin_hash:
        _agregar(hallazgos, "FAIL", "PASSWORD_SIN_HASH",
                 f"Cuentas con contraseña no hasheada: {', '.join(sin_hash)}.")
    else:
        _agregar(hallazgos, "OK", "PASSWORD_HASH",
                 f"Las {len(usuarios)} cuentas usan hash de contraseña.")

    pendientes = [u.username for u in usuarios if u.debe_cambiar_password]
    if pendientes:
        _agregar(hallazgos, "WARN", "PASSWORD_CAMBIO_PENDIENTE",
                 f"{len(pendientes)} cuenta(s) deben cambiar su contraseña temporal al ingresar.")


def auditar_integridad():
    """Ejecuta todas las verificaciones de solo lectura."""
    session = get_session()
    hallazgos = []
    try:
        if not _tabla_existe(session, "usuarios"):
            _agregar(hallazgos, "FAIL", "BD_VACIA",
                     "La tabla usuarios no existe; ejecuta inicializar_sistema.py.")
        else:
            _verificar_esquema(session, hallazgos)
            _verificar_huerfanos(session, hallazgos)
            _verificar_catalogos(session, hallazgos)
            _verificar_reportes(session, hallazgos)
            _verificar_decisiones(session, hallazgos)
            _verificar_compras_y_logs(session, hallazgos)
            _verificar_seguridad(session, hallazgos)
    finally:
        session.close()

    resumen = {"OK": 0, "WARN": 0, "FAIL": 0}
    for h in hallazgos:
        resumen[h.nivel] = resumen.get(h.nivel, 0) + 1

    return {
        "db": get_db_info(),
        "hallazgos": [asdict(h) for h in hallazgos],
        "resumen": resumen,
    }
