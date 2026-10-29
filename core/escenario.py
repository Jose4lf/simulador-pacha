"""
Escenario «El Mundo de Markestrat Bolivia» — PACHA
==================================================

Carga y valida el escenario de la industria de helados en Bolivia desde
``datos/escenario_bolivia.yaml`` y el catálogo de empresas y marcas desde
``datos/catalogo_productos.yaml``.

Este módulo es la **única puerta de entrada** al escenario: los servicios, el
motor, las semillas y las pruebas deben leer los parámetros por aquí y no
duplicar constantes.

Reglas que se validan al cargar
-------------------------------
1. Los 5 segmentos suman peso 1,00 y tienen número 1-5 único.
2. Los 3 canales suman cobertura 1,00 y tienen número 1-3 único.
3. Hay exactamente 6 atributos numerados 1-6, con ``minimo < maximo``.
4. Hay exactamente 15 estudios numerados 1-15, con costo positivo.
5. Todo dato declara ``naturaleza`` (oficial | supuesto | ficticio) y
   ``estado_verificacion`` (verificado | pendiente | no_aplica).
6. Un dato ``oficial`` debe citar ``fuente`` y ``fecha``.
7. Los atributos iniciales caben dentro de los rangos factibles.

Cualquier violación lanza ``ErrorEscenario`` con el detalle completo. La carga
es idempotente y se memoriza; usa ``recargar=True`` en pruebas.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ESCENARIO = RAIZ / "datos" / "escenario_bolivia.yaml"
RUTA_CATALOGO = RAIZ / "datos" / "catalogo_productos.yaml"

NATURALEZAS = {"oficial", "supuesto", "ficticio"}
ESTADOS_VERIFICACION = {"verificado", "pendiente", "no_aplica"}
TOTAL_SEGMENTOS = 5
TOTAL_CANALES = 3
TOTAL_ATRIBUTOS = 6
TOTAL_ESTUDIOS = 15
TOLERANCIA = 1e-6


class ErrorEscenario(ValueError):
    """El escenario o el catálogo no cumplen las reglas del simulador."""


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def _leer_yaml(ruta: Path):
    if not ruta.exists():
        raise ErrorEscenario(f"No se encontró el archivo de datos: {ruta}")
    with ruta.open("r", encoding="utf-8") as archivo:
        return yaml.safe_load(archivo)


@lru_cache(maxsize=4)
def _cargar_escenario_cache(ruta_str: str):
    datos = _leer_yaml(Path(ruta_str))
    _aplicar_valores_por_defecto(datos)
    validar_escenario(datos)
    return datos


def _aplicar_valores_por_defecto(datos):
    """Rellena los metadatos comunes de los estudios.

    Los 15 estudios comparten naturaleza y estado: son costos ficticios del
    ejercicio. Se declaran una sola vez en ``estudios_meta`` para no repetir
    cuatro líneas quince veces.
    """
    if not isinstance(datos, dict):
        return
    meta = datos.get("estudios_meta") or {}
    for estudio in datos.get("estudios") or []:
        if not isinstance(estudio, dict):
            continue
        estudio.setdefault("naturaleza", meta.get("naturaleza", "ficticio"))
        estudio.setdefault(
            "estado_verificacion", meta.get("estado_verificacion", "no_aplica")
        )


def cargar_escenario(ruta=None, recargar=False):
    """Devuelve el escenario validado como diccionario."""
    ruta = Path(ruta) if ruta else RUTA_ESCENARIO
    if recargar:
        _cargar_escenario_cache.cache_clear()
    return _cargar_escenario_cache(str(ruta))


@lru_cache(maxsize=4)
def _cargar_catalogo_cache(ruta_str: str):
    datos = _leer_yaml(Path(ruta_str))
    validar_catalogo(datos)
    return datos


def cargar_catalogo(ruta=None, recargar=False):
    """Devuelve el catálogo de empresas y marcas validado."""
    ruta = Path(ruta) if ruta else RUTA_CATALOGO
    if recargar:
        _cargar_catalogo_cache.cache_clear()
    return _cargar_catalogo_cache(str(ruta))


# ---------------------------------------------------------------------------
# Validación del escenario
# ---------------------------------------------------------------------------
def _validar_dato(nombre, dato, errores, exige_fuente_si_oficial=True):
    if not isinstance(dato, dict):
        errores.append(f"{nombre}: debe ser un mapa con valor y metadatos.")
        return
    if "valor" not in dato:
        errores.append(f"{nombre}: falta 'valor'.")
    naturaleza = dato.get("naturaleza")
    if naturaleza not in NATURALEZAS:
        errores.append(
            f"{nombre}: naturaleza '{naturaleza}' inválida "
            f"(usa {'/'.join(sorted(NATURALEZAS))})."
        )
    estado = dato.get("estado_verificacion")
    if estado not in ESTADOS_VERIFICACION:
        errores.append(
            f"{nombre}: estado_verificacion '{estado}' inválido "
            f"(usa {'/'.join(sorted(ESTADOS_VERIFICACION))})."
        )
    if exige_fuente_si_oficial and naturaleza == "oficial":
        if not str(dato.get("fuente") or "").strip():
            errores.append(f"{nombre}: un dato oficial debe citar 'fuente'.")
        if not str(dato.get("fecha") or "").strip():
            errores.append(f"{nombre}: un dato oficial debe citar 'fecha'.")


def _validar_metadatos(seccion, elemento, errores):
    """Comprueba naturaleza y estado_verificacion en elementos de lista."""
    prefijo = f"{seccion}[{elemento.get('numero')}]"
    if elemento.get("naturaleza") not in NATURALEZAS:
        errores.append(f"{prefijo}: 'naturaleza' inválida o ausente.")
    if elemento.get("estado_verificacion") not in ESTADOS_VERIFICACION:
        errores.append(f"{prefijo}: 'estado_verificacion' inválido o ausente.")


def _validar_lista(datos, seccion, total, errores):
    elementos = datos.get(seccion)
    if not isinstance(elementos, list):
        errores.append(f"{seccion}: debe ser una lista.")
        return []
    if len(elementos) != total:
        errores.append(f"{seccion}: se esperaban {total} elementos y hay {len(elementos)}.")
    numeros = [e.get("numero") for e in elementos if isinstance(e, dict)]
    if sorted(n for n in numeros if isinstance(n, int)) != list(range(1, total + 1)):
        errores.append(f"{seccion}: los números deben ser 1..{total} sin repetir.")
    return elementos


def validar_escenario(datos):
    """Valida el escenario completo. Lanza ``ErrorEscenario`` si algo falla."""
    errores = []

    if not isinstance(datos, dict):
        raise ErrorEscenario("El escenario debe ser un mapa YAML.")

    meta = datos.get("meta") or {}
    if not meta.get("codigo"):
        errores.append("meta.codigo es obligatorio.")
    if not meta.get("nombre"):
        errores.append("meta.nombre es obligatorio.")
    if meta.get("moneda") != "BOB":
        errores.append("meta.moneda debe ser BOB (bolivianos).")

    # --- Macro y mercado -------------------------------------------------
    macro = datos.get("macro") or {}
    if not macro:
        errores.append("Falta la sección 'macro'.")
    for clave, dato in macro.items():
        _validar_dato(f"macro.{clave}", dato, errores)

    mercado = datos.get("mercado") or {}
    if "mercado_potencial_base" not in mercado:
        errores.append("mercado.mercado_potencial_base es obligatorio.")
    for clave, dato in mercado.items():
        _validar_dato(f"mercado.{clave}", dato, errores)
    potencial = (mercado.get("mercado_potencial_base") or {}).get("valor")
    if not isinstance(potencial, (int, float)) or potencial <= 0:
        errores.append("mercado.mercado_potencial_base debe ser un número positivo.")

    # --- Segmentos -------------------------------------------------------
    segmentos = _validar_lista(datos, "segmentos", TOTAL_SEGMENTOS, errores)
    suma_pesos = 0.0
    for seg in segmentos:
        prefijo = f"segmentos[{seg.get('numero')}]"
        _validar_metadatos("segmentos", seg, errores)
        peso = seg.get("peso")
        if not isinstance(peso, (int, float)) or peso <= 0:
            errores.append(f"{prefijo}: 'peso' debe ser un número positivo.")
        else:
            suma_pesos += float(peso)
        for campo in (
            "elasticidad_precio", "respuesta_publicidad",
            "peso_cobertura", "peso_calidad",
        ):
            valor = seg.get(campo)
            if not isinstance(valor, (int, float)) or valor < 0:
                errores.append(f"{prefijo}: '{campo}' debe ser un número no negativo.")
        composicion = seg.get("preferencia_composicion") or {}
        if set(composicion) != {"agua", "mixto", "crema"}:
            errores.append(
                f"{prefijo}: preferencia_composicion debe tener agua, mixto y crema."
            )
        elif abs(sum(float(v) for v in composicion.values()) - 1.0) > TOLERANCIA:
            errores.append(f"{prefijo}: las preferencias de composición deben sumar 1,00.")
    if abs(suma_pesos - 1.0) > TOLERANCIA:
        errores.append(f"segmentos: los pesos suman {suma_pesos:.6f} y deben sumar 1,00.")

    # --- Canales ---------------------------------------------------------
    canales = _validar_lista(datos, "canales", TOTAL_CANALES, errores)
    suma_cobertura = 0.0
    for canal in canales:
        prefijo = f"canales[{canal.get('numero')}]"
        _validar_metadatos("canales", canal, errores)
        cobertura = canal.get("cobertura")
        if not isinstance(cobertura, (int, float)) or cobertura <= 0:
            errores.append(f"{prefijo}: 'cobertura' debe ser un número positivo.")
        else:
            suma_cobertura += float(cobertura)
        for campo in ("margen_canal", "costo_logistico", "exigencia_calidad"):
            valor = canal.get(campo)
            if not isinstance(valor, (int, float)) or not (0.0 <= valor < 1.0):
                errores.append(f"{prefijo}: '{campo}' debe estar entre 0 y 1.")
        puntos = canal.get("puntos_de_venta")
        if not isinstance(puntos, int) or puntos <= 0:
            errores.append(f"{prefijo}: 'puntos_de_venta' debe ser un entero positivo.")
    if abs(suma_cobertura - 1.0) > TOLERANCIA:
        errores.append(
            f"canales: la cobertura suma {suma_cobertura:.6f} y debe sumar 1,00."
        )

    # --- Atributos -------------------------------------------------------
    atributos = datos.get("atributos") or {}
    lista = _validar_lista(atributos, "lista", TOTAL_ATRIBUTOS, errores)
    rangos = {}
    for atributo in lista:
        numero = atributo.get("numero")
        prefijo = f"atributos[{numero}]"
        if not atributo.get("codigo") or not atributo.get("nombre"):
            errores.append(f"{prefijo}: 'codigo' y 'nombre' son obligatorios.")
        minimo, maximo = atributo.get("minimo"), atributo.get("maximo")
        if not isinstance(minimo, (int, float)) or not isinstance(maximo, (int, float)):
            errores.append(f"{prefijo}: 'minimo' y 'maximo' deben ser numéricos.")
            continue
        if minimo >= maximo:
            errores.append(f"{prefijo}: 'minimo' debe ser menor que 'maximo'.")
        rangos[numero] = (float(minimo), float(maximo))
        if not isinstance(atributo.get("coeficiente_costo"), (int, float)):
            errores.append(f"{prefijo}: falta 'coeficiente_costo'.")
        if not isinstance(atributo.get("presupuesto_por_unidad"), (int, float)):
            errores.append(f"{prefijo}: falta 'presupuesto_por_unidad'.")

    iniciales = datos.get("atributos_iniciales") or {}
    for numero, (minimo, maximo) in rangos.items():
        valor = iniciales.get(numero)
        if not isinstance(valor, (int, float)):
            errores.append(f"atributos_iniciales: falta el atributo {numero}.")
        elif not (minimo <= float(valor) <= maximo):
            errores.append(
                f"atributos_iniciales[{numero}] = {valor} fuera del rango "
                f"{minimo:g}-{maximo:g}."
            )

    # --- Motor -----------------------------------------------------------
    motor = datos.get("motor") or {}
    obligatorios = (
        "escala_awareness", "sigma_calidad", "sigma_cremosidad", "sigma_empaque",
        "costo_fijo_por_marca", "costo_vendedor", "presupuesto_inicial",
        "merma_anual_inventario", "costo_almacenaje",
        "vendedores_plenos", "peso_detallistas", "peso_vendedores",
    )
    for clave in obligatorios:
        if not isinstance(motor.get(clave), (int, float)):
            errores.append(f"motor.{clave} es obligatorio y debe ser numérico.")

    # --- Estudios --------------------------------------------------------
    estudios = _validar_lista(datos, "estudios", TOTAL_ESTUDIOS, errores)
    for estudio in estudios:
        prefijo = f"estudios[{estudio.get('numero')}]"
        _validar_metadatos("estudios", estudio, errores)
        if not estudio.get("nombre"):
            errores.append(f"{prefijo}: falta 'nombre'.")
        costo = estudio.get("costo_base")
        if not isinstance(costo, (int, float)) or costo <= 0:
            errores.append(f"{prefijo}: 'costo_base' debe ser un número positivo.")

    if errores:
        detalle = "\n".join(f"  - {e}" for e in errores)
        raise ErrorEscenario(f"Escenario inválido:\n{detalle}")
    return True


# ---------------------------------------------------------------------------
# Validación del catálogo
# ---------------------------------------------------------------------------
def validar_catalogo(datos):
    """Valida el catálogo de empresas y marcas."""
    errores = []

    if not isinstance(datos, dict):
        raise ErrorEscenario("El catálogo debe ser un mapa YAML.")

    empresas = datos.get("empresas")
    if not isinstance(empresas, list) or len(empresas) != 5:
        errores.append("catalogo.empresas: se esperaban 5 empresas.")

    codigos_empresa = set()
    for empresa in empresas or []:
        codigo = (empresa or {}).get("codigo")
        if not codigo:
            errores.append("catalogo.empresas: toda empresa necesita 'codigo'.")
            continue
        if codigo in codigos_empresa:
            errores.append(f"catalogo.empresas: código repetido '{codigo}'.")
        codigos_empresa.add(codigo)
        if empresa.get("naturaleza") not in NATURALEZAS:
            errores.append(f"empresa '{codigo}': naturaleza inválida.")
        if empresa.get("estado_verificacion") not in ESTADOS_VERIFICACION:
            errores.append(f"empresa '{codigo}': estado_verificacion inválido.")

    marcas = datos.get("marcas")
    if not isinstance(marcas, list) or len(marcas) != 10:
        errores.append("catalogo.marcas: se esperaban 10 marcas.")

    codigos_marca = set()
    for marca in marcas or []:
        codigo = (marca or {}).get("codigo")
        if not codigo:
            errores.append("catalogo.marcas: toda marca necesita 'codigo'.")
            continue
        if codigo in codigos_marca:
            errores.append(f"catalogo.marcas: código repetido '{codigo}'.")
        codigos_marca.add(codigo)
        if marca.get("empresa") not in codigos_empresa:
            errores.append(f"marca '{codigo}': empresa '{marca.get('empresa')}' inexistente.")
        if marca.get("naturaleza") not in NATURALEZAS:
            errores.append(f"marca '{codigo}': naturaleza inválida.")
        if marca.get("estado_verificacion") not in ESTADOS_VERIFICACION:
            errores.append(f"marca '{codigo}': estado_verificacion inválido.")
        if len(str(marca.get("nombre") or "")) > 30:
            errores.append(f"marca '{codigo}': el nombre supera 30 caracteres.")

    lineas = datos.get("lineas") or {}
    for nombre in ("agua", "mixto", "crema"):
        if nombre not in lineas:
            errores.append(f"catalogo.lineas: falta la línea '{nombre}'.")
            continue
        precio = lineas[nombre].get("precio_inicial")
        if not isinstance(precio, (int, float)) or precio <= 0:
            errores.append(f"catalogo.lineas.{nombre}: 'precio_inicial' inválido.")
        if marcas and not any(m.get("linea") == nombre for m in marcas):
            errores.append(f"catalogo.lineas: ninguna marca usa la línea '{nombre}'.")

    if errores:
        detalle = "\n".join(f"  - {e}" for e in errores)
        raise ErrorEscenario(f"Catálogo inválido:\n{detalle}")
    return True


# ---------------------------------------------------------------------------
# Accesos cómodos
# ---------------------------------------------------------------------------
def valor(dato):
    """Devuelve el valor numérico de un dato con metadatos."""
    return float((dato or {}).get("valor") or 0)


def mercado_potencial(escenario=None):
    """Mercado potencial base en unidades físicas."""
    escenario = escenario or cargar_escenario()
    return valor(escenario["mercado"]["mercado_potencial_base"])


def crecimiento_anual(escenario=None):
    escenario = escenario or cargar_escenario()
    return valor(escenario["mercado"]["crecimiento_anual"])


def segmentos(escenario=None):
    return list((escenario or cargar_escenario())["segmentos"])


def canales(escenario=None):
    return list((escenario or cargar_escenario())["canales"])


def estudios(escenario=None):
    return list((escenario or cargar_escenario())["estudios"])


def parametros_motor(escenario=None):
    return dict((escenario or cargar_escenario())["motor"])


def atributos(escenario=None):
    return list((escenario or cargar_escenario())["atributos"]["lista"])


def rangos_atributos(escenario=None):
    return {
        int(a["numero"]): (float(a["minimo"]), float(a["maximo"]))
        for a in atributos(escenario)
    }


def mapa_composicion():
    """Convierte el nombre de la línea en el valor numérico del atributo 1."""
    return {"agua": 0.0, "mixto": 1.0, "crema": 2.0}


def costo_estandar(atributos_marca, escenario=None):
    """Costo estándar de producción (Bs/unidad) según los atributos 1-5.

    Usa ``costo_base`` y los ``coeficiente_costo`` declarados en el escenario.
    El atributo 6 no entra en la fórmula: es el costo objetivo de I&D.
    """
    escenario = escenario or cargar_escenario()
    bloque = escenario["atributos"]
    total = float(bloque.get("costo_base") or 0.0)
    for atributo in bloque["lista"]:
        numero = int(atributo["numero"])
        if numero == TOTAL_ATRIBUTOS:
            continue
        total += float(atributo["coeficiente_costo"]) * float(
            atributos_marca.get(numero, 0) or 0
        )
    return round(total, 2)


def peso_estacionalidad(mes, escenario=None):
    """Peso de consumo del mes (1-12), normalizado a promedio 1,0.

    El motor solo lo usa de forma informativa; el mercado anual ya está
    expresado en unidades por año.
    """
    escenario = escenario or cargar_escenario()
    meses = list((escenario.get("estacionalidad") or {}).get("meses", {}).values())
    if not meses:
        return 1.0
    if not 1 <= int(mes) <= len(meses):
        raise ValueError("El mes debe estar entre 1 y 12.")
    promedio = sum(float(m) for m in meses) / len(meses)
    if promedio <= 0:
        return 1.0
    return round(float(meses[int(mes) - 1]) / promedio, 4)


def resumen(escenario=None, catalogo=None):
    """Resumen legible del escenario para pantallas de administración."""
    escenario = escenario or cargar_escenario()
    catalogo = catalogo or cargar_catalogo()
    macro = escenario["macro"]
    return {
        "codigo": escenario["meta"]["codigo"],
        "nombre": escenario["meta"]["nombre"],
        "version": escenario["meta"]["version"],
        "industria": escenario["meta"]["industria"],
        "moneda": escenario["meta"]["simbolo_moneda"],
        "mercado_potencial": mercado_potencial(escenario),
        "segmentos": len(escenario["segmentos"]),
        "canales": len(escenario["canales"]),
        "atributos": len(escenario["atributos"]["lista"]),
        "estudios": len(escenario["estudios"]),
        "empresas": len(catalogo["empresas"]),
        "marcas": len(catalogo["marcas"]),
        "inflacion_anual": valor(macro["inflacion_anual"]),
        "tipo_cambio_usd": valor(macro["tipo_cambio_usd"]),
        "crecimiento_pib": valor(macro["crecimiento_pib"]),
        "datos_pendientes": _contar_pendientes(escenario),
        "descargo": escenario["meta"]["descargo"].strip(),
    }


def _contar_pendientes(nodo):
    """Cuenta los datos con ``estado_verificacion: pendiente`` en el escenario."""
    if isinstance(nodo, dict):
        if nodo.get("estado_verificacion") == "pendiente":
            return 1
        return sum(_contar_pendientes(v) for v in nodo.values())
    if isinstance(nodo, list):
        return sum(_contar_pendientes(v) for v in nodo)
    return 0


def techo_mercado(escenario=None, ciclos=10):
    """Mercado proyectado al año ``ciclos`` (informativo, sin redondear)."""
    base = mercado_potencial(escenario)
    return round(base * math.pow(1.0 + crecimiento_anual(escenario), ciclos), 0)
