"""
Modelo de I&D — PACHA (Etapa 5)
===============================

Implementa las reglas que el Manual del participante ya documenta para el
Centro de I&D de Sonite. **No reproduce fórmulas propietarias de LABSAG**: usa
las tablas publicadas en el manual del propio proyecto y las deja explícitas
aquí para que cualquier resultado sea auditable.

Reglas implementadas
--------------------
1. Un proyecto tiene 6 atributos objetivo dentro de los rangos factibles del
   Cuadro 2 y un presupuesto en miles de Bs (100 a 1000 para Sonite).
2. El costo estándar del producto se obtiene multiplicando los atributos
   1-5 por sus coeficientes de costo.
3. El presupuesto "normal" de I&D es la suma del esfuerzo por unidad de cambio
   de cada atributo, más 10 miles de Bs por cada Bs de reducción del costo
   objetivo (atributo 6).
4. La probabilidad de aprobación es ``presupuesto_asignado / presupuesto_normal``
   (máximo 1). Si el costo objetivo supera en más de 30 % el costo estándar, el
   proyecto fracasa automáticamente.
5. El resultado se decide con un sorteo determinista (semilla de la industria,
   equipo, nombre de proyecto y año), de modo que reprocesar no cambia el
   resultado.
6. Un proyecto aprobado queda disponible para aplicarse a una marca en la hoja
   de decisiones del año siguiente. El proyecto toma un año.

Índice de calidad
-----------------
El manual no define un índice de calidad único. PACHA usa un índice propio
(0-100) que normaliza los cinco atributos físicos dentro de su rango factible,
considerando deseables un menor peso y volumen y un mayor diseño, frecuencia y
potencia. Se usa solo como factor de atractivo del motor y se documenta para
que sea reproducible; no es una fórmula oficial de LABSAG.
"""
import hashlib
import random

RANGOS_SONITE = {
    1: (10.0, 20.0),   # peso (kg)
    2: (3.0, 10.0),    # diseño (índice)
    3: (20.0, 100.0),  # volumen (dm3)
    4: (5.0, 50.0),    # frecuencia máxima (MHz)
    5: (5.0, 100.0),   # potencia (W)
    6: (50.0, 500.0),  # costo objetivo (Bs)
}

# Coeficientes del costo estándar (Bs por unidad de atributo).
COEFICIENTES_COSTO_SONITE = {
    1: 0.15, 2: 4.70, 3: 0.25, 4: 0.80, 5: 1.50,
}

# Presupuesto normal de I&D por unidad de cambio (miles de Bs).
PRESUPUESTO_POR_UNIDAD = {
    1: 30.0, 2: 70.0, 3: 15.0, 4: 20.0, 5: 20.0,
}
PRESUPUESTO_POR_COSTO = 10.0  # miles de Bs por cada Bs de reducción

PRESUPUESTO_MINIMO = 100.0   # miles de Bs
PRESUPUESTO_MAXIMO = 1000.0  # miles de Bs
COSTO_SOBRE_ESTANDAR_MAXIMO = 0.30
MAX_PROYECTOS_POR_ANIO = 4
MAX_PROYECTOS_POR_SIMULACION = 5
NOMBRE_VALIDO = r"^P[SV][A-Z]{3}$"

NOMBRES_ATRIBUTOS = {
    1: "Peso",
    2: "Diseño",
    3: "Volumen",
    4: "Frecuencia",
    5: "Potencia",
    6: "Costo",
}


def _r(valor, decimales=2):
    return round(float(valor), decimales)


def costo_estandar(atributos):
    """Costo estándar en Bs según los atributos 1-5."""
    return _r(sum(
        float(atributos.get(numero, 0) or 0) * coeficiente
        for numero, coeficiente in COEFICIENTES_COSTO_SONITE.items()
    ))


def validar_atributos(atributos):
    """Devuelve (ok, mensaje). Exige los 6 atributos dentro de rango."""
    if not isinstance(atributos, dict):
        return False, "Los atributos deben enviarse como lista de 6 valores."
    for numero, (minimo, maximo) in RANGOS_SONITE.items():
        if numero not in atributos:
            return False, f"Falta el atributo {numero} ({NOMBRES_ATRIBUTOS[numero]})."
        try:
            valor = float(atributos[numero])
        except (TypeError, ValueError):
            return False, f"El atributo {numero} no es numérico."
        if valor < minimo or valor > maximo:
            return False, (
                f"{NOMBRES_ATRIBUTOS[numero]} = {valor:g} fuera del rango "
                f"factible {minimo:g}-{maximo:g}."
            )
    return True, ""


def validar_nombre(nombre):
    """Nombre de proyecto: P + S/V + tres letras (por ejemplo PSAMA)."""
    import re
    return bool(re.match(NOMBRE_VALIDO, (nombre or "").strip().upper()))


def presupuesto_requerido(actuales, objetivo):
    """Presupuesto normal de I&D en miles de Bs.

    ``actuales`` y ``objetivo`` son dicts {1..6: valor}. Para una marca nueva,
    ``actuales`` debe ser el perfil de referencia del equipo.
    """
    total = 0.0
    for numero, tarifa in PRESUPUESTO_POR_UNIDAD.items():
        total += abs(
            float(objetivo.get(numero, 0) or 0)
            - float(actuales.get(numero, 0) or 0)
        ) * tarifa
    reduccion_costo = max(
        0.0,
        float(actuales.get(6, 0) or 0) - float(objetivo.get(6, 0) or 0),
    )
    total += reduccion_costo * PRESUPUESTO_POR_COSTO
    return _r(total)


def probabilidad_exito(presupuesto_miles, presupuesto_normal_miles):
    """Probabilidad proporcional al presupuesto (regla del 70 % del manual)."""
    if presupuesto_normal_miles <= 0:
        return 1.0
    return _r(min(1.0, max(0.0, float(presupuesto_miles) / presupuesto_normal_miles)), 4)


def indice_calidad(atributos):
    """Índice propio 0-100 a partir de los atributos físicos 1-5."""
    deseables = {
        1: lambda v: (20.0 - v) / 10.0,
        2: lambda v: (v - 3.0) / 7.0,
        3: lambda v: (100.0 - v) / 80.0,
        4: lambda v: (v - 5.0) / 45.0,
        5: lambda v: (v - 5.0) / 95.0,
    }
    valores = []
    for numero, funcion in deseables.items():
        minimo, maximo = RANGOS_SONITE[numero]
        valor = min(maximo, max(minimo, float(atributos.get(numero, minimo) or minimo)))
        valores.append(min(1.0, max(0.0, funcion(valor))))
    return _r(sum(valores) / len(valores) * 100.0)


def _atributo_mas_costoso(actuales, objetivo):
    """Atributo 1-6 que concentra el mayor esfuerzo económico."""
    esfuerzos = {}
    for numero, tarifa in PRESUPUESTO_POR_UNIDAD.items():
        esfuerzos[numero] = abs(
            float(objetivo.get(numero, 0) or 0)
            - float(actuales.get(numero, 0) or 0)
        ) * tarifa
    reduccion = max(
        0.0,
        float(actuales.get(6, 0) or 0) - float(objetivo.get(6, 0) or 0),
    ) * PRESUPUESTO_POR_COSTO
    esfuerzos[6] = reduccion
    return max(esfuerzos, key=esfuerzos.get)


def _sorteo(semilla, anio, equipo_id, nombre):
    clave = f"{semilla}|{anio}|{equipo_id}|{(nombre or '').upper()}"
    valor = int(hashlib.sha256(clave.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(valor).random()


def evaluar_proyecto(actuales, objetivo, presupuesto_miles, *, equipo_id=0,
                     nombre="", anio=0, semilla="pacha"):
    """Evalúa un proyecto y devuelve el resultado documentado.

    Devuelve un dict con ``aprobado``, ``probabilidad``, ``presupuesto_normal``,
    ``costo_estandar``, ``atributo_fallido``, ``presupuesto_adicional``,
    ``costo_minimo`` y ``detalle``.
    """
    presupuesto_normal = presupuesto_requerido(actuales, objetivo)
    estandar = costo_estandar(objetivo)
    costo_objetivo = float(objetivo.get(6, 0) or 0)
    probabilidad = probabilidad_exito(presupuesto_miles, presupuesto_normal)

    resultado = {
        "aprobado": False,
        "probabilidad": probabilidad,
        "presupuesto_normal": presupuesto_normal,
        "presupuesto_asignado": _r(presupuesto_miles),
        "costo_estandar": estandar,
        "costo_objetivo": _r(costo_objetivo),
        "atributo_fallido": None,
        "presupuesto_adicional": 0.0,
        "costo_minimo": None,
        "detalle": "",
    }

    # Fracaso automático: costo objetivo demasiado alto para el producto.
    limite = estandar * (1.0 + COSTO_SOBRE_ESTANDAR_MAXIMO)
    if costo_objetivo > limite + 0.01:
        resultado.update({
            "atributo_fallido": 6,
            "costo_minimo": estandar,
            "detalle": (
                f"El costo objetivo {costo_objetivo:,.2f} Bs supera en más del "
                f"30 % el costo estándar {estandar:,.2f} Bs. Costo mínimo "
                f"realista: {estandar:,.2f} Bs."
            ),
        })
        return resultado

    # Sorteo determinista: se aprueba si el número aleatorio cae dentro de la
    # probabilidad calculada.
    if _sorteo(semilla, anio, equipo_id, nombre) <= probabilidad:
        resultado.update({"aprobado": True, "detalle": "Proyecto aprobado por I&D."})
        return resultado

    fallido = _atributo_mas_costoso(actuales, objetivo)
    falta = max(0.0, presupuesto_normal - float(presupuesto_miles))
    resultado.update({
        "atributo_fallido": fallido,
        "presupuesto_adicional": _r(falta if falta > 0 else presupuesto_normal * 0.1),
        "detalle": (
            f"El proyecto no alcanzó el presupuesto normal. Atributo crítico: "
            f"{NOMBRES_ATRIBUTOS.get(fallido, fallido)}. "
            f"Presupuesto adicional sugerido: "
            f"{_r(falta if falta > 0 else presupuesto_normal * 0.1):,.2f} miles de Bs."
        ),
    })
    return resultado
