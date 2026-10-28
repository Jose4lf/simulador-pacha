"""
Reporte de Año 0 — PACHA (Etapa 4)
==================================

El Año 0 es el diagnóstico inicial de la simulación: no es una ronda del
motor, sino la foto de partida de cada empresa. Este módulo construye esa foto
con **las mismas unidades que el motor** para que los reportes sean auditables:

- ``mercado_total``: unidades físicas (1.300.000).
- ``produccion``, ``unidades_vendidas``, ``inventario``: **miles de unidades**.
- ``precio``: Bs por unidad.
- ``publicidad``, ``ingresos``, ``costos`` y ``contribución``: **miles de Bs**.

Reglas del Año 0
----------------
1. La participación inicial de cada marca sale de ``PORCIONES_INICIALES``
   (perfil histórico del escenario Markestrated) normalizada a 100 %.
2. Se vende toda la producción: ``inventario = 0`` y
   ``unidades_vendidas = producción``.
3. El costo de transferencia es el atributo físico 6 (costo estándar pedido a
   I&D). Si la marca no tiene atributos registrados se usa el 55 % del precio,
   igual que el valor por defecto del motor.
4. La contribución bruta de marketing descuenta publicidad y fuerza de ventas,
   tal como la calcula ``MotorSimulacion``.
5. La contribución neta de la empresa descuenta el costo fijo por marca
   (500 miles de Bs). En Año 0 no hay gastos de I&D ni estudios.
6. Las ventas por segmento se reparten según el peso de cada segmento. El Año 0
   no tiene diferenciación por segmento, así que la participación dentro de
   cada segmento es la participación global de la marca.
"""
from core.models import (
    AtributoFisico, Canal, Equipo, FuerzaVentas, Marca, Reporte, ReporteMarca,
    ReporteMarcaCanal, ReporteMarcaSegmento, Segmento,
)
from core.motor_simulacion import MotorSimulacion

MERCADO_BASE = float(MotorSimulacion.MERCADO_BASE)
COSTO_FIJO_POR_MARCA = float(MotorSimulacion.COSTO_FIJO_POR_MARCA)
COSTO_VENDEDOR = float(MotorSimulacion.COSTO_VENDEDOR)
MARGEN_TRANSFERENCIA = float(MotorSimulacion.MARGEN_TRANSFERENCIA)

# Participación inicial por número de equipo (porcentajes del mercado).
# Suman 96 %; se normalizan a 100 % para que la auditoría de participación
# cierre exactamente.
PORCIONES_INICIALES = {
    1: [11.0, 4.0],
    2: [8.0, 6.0],
    3: [15.0, 10.0],
    4: [20.0, 15.0],
    5: [5.0, 2.0],
}


def porciones_equipo(numero_equipo, cantidad_marcas):
    """Participaciones históricas (en %) de las marcas del equipo.

    Son porcentajes del mercado total, no de la empresa: la suma de todos los
    equipos del escenario es 96 %. ``generar_reporte_anio0`` los reescala para
    que el conjunto de equipos presentes cubra el 100 %.
    """
    base = list(PORCIONES_INICIALES.get(numero_equipo, PORCIONES_INICIALES[1]))
    if cantidad_marcas <= 0:
        return []
    if cantidad_marcas <= len(base):
        return base[:cantidad_marcas]
    return base + [0.0] * (cantidad_marcas - len(base))


def factor_participacion(session, industria):
    """Escala para que las participaciones de los equipos sumen 100 %."""
    equipos = session.query(Equipo).filter_by(
        industria_id=industria.id
    ).all()
    total = 0.0
    for equipo in equipos:
        cantidad = session.query(Marca).filter_by(
            equipo_id=equipo.id, activa=True
        ).count()
        total += sum(porciones_equipo(equipo.numero, cantidad))
    if total <= 0:
        return 1.0
    return 100.0 / total


def _r(valor, decimales=2):
    return round(float(valor), decimales)


def _atributos_de_marca(session, marca):
    filas = session.query(AtributoFisico).filter_by(marca_id=marca.id).order_by(
        AtributoFisico.anio.asc(), AtributoFisico.numero.asc()
    ).all()
    if not filas:
        return {}
    anio_base = 0 if any(f.anio == 0 for f in filas) else filas[-1].anio
    return {
        f.numero: float(f.valor or 0)
        for f in filas
        if f.anio == anio_base
    }


def _fuerza_ventas_de_marca(session, marca, canales):
    """Última fila de fuerza de ventas por canal (Año 0 o la más reciente)."""
    vendedores = {}
    detallistas = {}
    for canal in canales:
        fila = session.query(FuerzaVentas).filter_by(
            marca_id=marca.id, canal_id=canal.id
        ).order_by(FuerzaVentas.anio.desc()).first()
        vendedores[canal.id] = int(fila.vendedores or 0) if fila else 0
        detallistas[canal.id] = int(fila.detallistas or 0) if fila else 0
    return vendedores, detallistas


def _repartir(total, pesos):
    """Reparte ``total`` según ``pesos`` y ajusta el último tramo al resto."""
    pesos = [max(0.0, float(p or 0)) for p in pesos]
    suma = sum(pesos)
    if suma <= 0:
        pesos = [1.0] * len(pesos)
        suma = float(len(pesos))
    tramos = [_r(total * p / suma) for p in pesos]
    if tramos:
        tramos[-1] = _r(total - sum(tramos[:-1]))
    return tramos


def generar_reporte_anio0(session, equipo, industria):
    """Construye (sin guardar) el ``Reporte`` de Año 0 de un equipo.

    Devuelve un objeto ``Reporte`` con sus marcas, canales y segmentos ya
    enlazados. El llamador decide si lo agrega a la sesión.
    """
    marcas = session.query(Marca).filter_by(
        equipo_id=equipo.id, activa=True
    ).order_by(Marca.id).all()
    canales = session.query(Canal).filter_by(
        industria_id=industria.id
    ).order_by(Canal.numero).all()
    segmentos = session.query(Segmento).filter_by(
        industria_id=industria.id
    ).order_by(Segmento.numero).all()

    porciones = porciones_equipo(equipo.numero, len(marcas))
    escala = factor_participacion(session, industria)

    reporte = Reporte(
        equipo_id=equipo.id,
        anio=0,
        mercado_total=MERCADO_BASE,
        contribucion_bruta_total=0.0,
        contribucion_neta_total=0.0,
        presupuesto_proximo_periodo=0.0,
        investigacion_total=0.0,
        fuerza_ventas_total=0.0,
        investigacion_mercado=0.0,
        costo_util_excepcional=0.0,
        inflacion_aplicada=industria.inflacion_anual,
        crecimiento_pnb=industria.crecimiento_pib,
        tipo_cambio=industria.tipo_cambio_usd,
    )

    total_bruta = 0.0
    total_fv = 0.0

    for idx, marca in enumerate(marcas):
        porcion = float(porciones[idx]) * escala if idx < len(porciones) else 0.0
        ventas_miles = _r(MERCADO_BASE * porcion / 100.0 / 1000.0)
        produccion_miles = ventas_miles
        inventario_miles = 0.0

        atributos = _atributos_de_marca(session, marca)
        precio = float(marca.precio_actual or 0)
        costo_unitario = float(
            atributos.get(6) or precio * MARGEN_TRANSFERENCIA
        )
        publicidad = float(marca.publicidad_actual or 0)

        vendedores, detallistas = _fuerza_ventas_de_marca(
            session, marca, canales
        )
        costo_fv = sum(vendedores.values()) * COSTO_VENDEDOR

        ingresos = _r(precio * ventas_miles)
        costo_productos = _r(costo_unitario * ventas_miles)
        costo_inventario = 0.0
        contribucion = _r(
            ingresos - costo_productos - costo_inventario
            - publicidad - costo_fv
        )

        total_bruta += contribucion
        total_fv += costo_fv

        rm = ReporteMarca(
            marca_nombre=marca.nombre,
            produccion=produccion_miles,
            unidades_vendidas=ventas_miles,
            inventario=inventario_miles,
            precio_final=precio,
            precio_promedio=precio,
            costo_transferencia=_r(costo_unitario),
            ingresos=ingresos,
            costo_productos_vendidos=costo_productos,
            costo_inventario=costo_inventario,
            publicidad=_r(publicidad),
            contribucion_bruta_marketing=contribucion,
            porcion_mercado=_r(porcion),
        )

        if canales:
            pesos = []
            for canal in canales:
                total_canal = max(1.0, float(canal.total_distribuidores or 1))
                pesos.append(
                    vendedores.get(canal.id, 0)
                    + detallistas.get(canal.id, 0) / 100.0
                    + total_canal / 1000.0
                )
            ventas_canal = _repartir(ventas_miles, pesos)
            for canal, ventas in zip(canales, ventas_canal):
                rm.canales.append(ReporteMarcaCanal(
                    canal_id=canal.id,
                    vendedores=vendedores.get(canal.id, 0),
                    detallistas=detallistas.get(canal.id, 0),
                    ventas_unidades=ventas,
                ))

        if segmentos:
            pesos = [float(s.peso or 0) for s in segmentos]
            ventas_segmento = _repartir(ventas_miles, pesos)
            for segmento, ventas in zip(segmentos, ventas_segmento):
                rm.segmentos.append(ReporteMarcaSegmento(
                    segmento_id=segmento.id,
                    ventas_unidades=ventas,
                    porcion_mercado=_r(porcion),
                ))

        reporte.marcas.append(rm)

    costo_fijo = COSTO_FIJO_POR_MARCA * len(marcas)
    neta = _r(total_bruta - costo_fijo)
    reporte.contribucion_bruta_total = _r(total_bruta)
    reporte.contribucion_neta_total = neta
    reporte.fuerza_ventas_total = _r(total_fv)
    reporte.costo_util_excepcional = _r(costo_fijo)
    reporte.presupuesto_proximo_periodo = _r(max(
        float(industria.presupuesto_inicial or 10000),
        neta * 0.3,
    ))

    return reporte
