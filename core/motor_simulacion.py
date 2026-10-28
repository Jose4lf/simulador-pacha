"""
Motor de simulación MARKESTRATED — PACHA (Etapa 3)
==================================================

Modelo propio y reproducible. No reproduce las fórmulas propietarias de
LABSAG: implementa un mercado de competencia monopolística con 5 segmentos y
3 canales, documentado aquí para que cualquier resultado pueda auditarse.

Unidades (consistentes en todo el motor y en los reportes):

- ``mercado_total``: unidades físicas. Base 1.300.000 unidades.
- ``produccion``, ``inventario``, ``unidades_vendidas``: **miles de unidades**
  (la hoja de decisiones y los reportes usan la etiqueta "Miles U").
- ``precio``: Bs por unidad.
- ``publicidad``, ``ingresos``, ``costos`` y ``contribución``: **miles de Bs**.

Fórmulas
--------
1. Tamaño de mercado::

       mercado(año) = 1.300.000 * (1 + crecimiento_pib) ** (año - año_base)

   La inflación no altera el volumen: solo encarece costos y precios.

2. Atractivo de la marca *i* en el segmento *s*::

       atractivo = f_precio * f_publicidad * f_distribucion * f_calidad * ruido

   - ``f_precio = (precio_promedio / precio_i) ** elasticidad_s``
   - ``f_publicidad = (publicidad_i / publicidad_promedio) ** 0.5``
   - ``f_distribucion`` combina vendedores y detallistas frente al promedio.
   - ``f_calidad = (calidad_i / calidad_promedio) ** 0.4``
   - ``ruido`` es determinista (±6%) y depende de semilla, año, segmento y marca.

   La elasticidad del segmento crece con ``valor_ideal_x`` (economía percibida):
   los segmentos más sensibles al precio castigan más un precio alto.

3. Reparto: la demanda de cada marca en cada segmento es
   ``mercado_segmento * atractivo_i / suma(atractivos)``.

4. Oferta: ``disponible = inventario_inicial + producción``. Si la demanda
   supera lo disponible, se vende todo lo disponible y el resto se registra
   como demanda no satisfecha (no se arrastra al año siguiente).

5. Canales: las ventas de la marca se reparten según el peso relativo de
   vendedores, detallistas y tamaño del canal.

6. Finanzas por marca (miles de Bs)::

       ingresos       = precio * vendidas_miles
    costo_transf   = costo_unitario de la marca (atributo 6 de I&D)
                     o precio * 0.55 si la marca no tiene costo propio
       costo_productos= costo_transf * vendidas_miles
       costo_inventario = costo_transf * inventario_final_miles * 0.115
       contribución   = ingresos - costo_productos - costo_inventario
                        - publicidad - costo_fuerza_ventas

   El costo fijo por marca y los gastos corporativos (I+D, estudios, costo
   util/excepcional) se restan a nivel de empresa en el servicio de simulación.
"""
import hashlib
import random


class MotorSimulacion:
    """Motor que simula el mercado de refrescos MARKESTRATED."""

    # Constantes del modelo (miles de Bs salvo indicación contraria)
    COSTO_FIJO_POR_MARCA = 500
    COSTO_VARIABLE_UNITARIO = 50  # Bs por unidad
    COSTO_ALMACENAJE_PORC = 0.115
    COSTO_VENDEDOR = 30.6  # miles de Bs por vendedor
    PRESUPUESTO_INICIAL = 10000
    MARGEN_TRANSFERENCIA = 0.55
    MERCADO_BASE = 1300000

    def __init__(self, config):
        """
        config: dict con parámetros de la industria.
            - mercado_total: unidades (por defecto 1.300.000)
            - crecimiento_pib: crecimiento anual del mercado (por defecto 0.04)
            - inflacion_anual: informativa; no altera el volumen
            - anio_base: año de referencia del mercado (por defecto 0)
            - semilla: texto para el ruido determinista (por defecto "pacha")
        """
        self.config = config or {}
        self.mercado_base = float(self.config.get("mercado_total", self.MERCADO_BASE))
        self.inflacion_anual = float(self.config.get("inflacion_anual", 0.09))
        self.crecimiento_pib = float(self.config.get("crecimiento_pib", 0.04))
        self.anio_base = int(self.config.get("anio_base", 0))
        self.semilla = str(self.config.get("semilla", "pacha"))

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def simular_ronda(self, marcas_data, segmentos, canales, anio, industria_config=None):
        """Simula una ronda completa y devuelve resultados por marca."""
        marcas = [self._normalizar_marca(m) for m in (marcas_data or [])]
        if not marcas:
            return {
                "resultados": [], "mercado_total": self._calcular_mercado(anio),
                "anio": anio, "factor_mercado": 1.0,
            }

        segmentos = list(segmentos or [])
        canales = list(canales or [])
        if not segmentos:
            segmentos = [{"id": None, "numero": 1, "peso": 1.0, "valor_ideal_x": 0}]
        if not canales:
            canales = [{"id": None, "numero": 1, "total_distribuidores": 1}]

        mercado_total = self._calcular_mercado(anio)
        peso_total = sum(max(0.0, float(s.get("peso") or 0)) for s in segmentos)
        if peso_total <= 0:
            peso_total = float(len(segmentos))

        promedios = self._promedios(marcas)
        n = len(marcas)
        demanda_unidades = [0.0] * n
        demanda_por_segmento = [[0.0] * len(segmentos) for _ in range(n)]

        # 1) Reparto del mercado por segmento.
        for idx_seg, seg in enumerate(segmentos):
            peso = max(0.0, float(seg.get("peso") or 0)) / peso_total
            mercado_seg = mercado_total * peso
            atractivos = [
                self._atractivo(m, promedios, seg, anio, idx_seg, idx) for idx, m in enumerate(marcas)
            ]
            total_atractivo = sum(atractivos)
            if total_atractivo <= 0:
                atractivos = [1.0] * n
                total_atractivo = float(n)

            for idx in range(n):
                porcion = atractivos[idx] / total_atractivo
                demanda = mercado_seg * porcion
                demanda_unidades[idx] += demanda
                demanda_por_segmento[idx][idx_seg] = demanda

        # 2) Restricción de oferta y cálculo de inventario final.
        resultados = []
        for idx, marca in enumerate(marcas):
            disponible = max(0.0, marca["inventario"] + marca["produccion"]) * 1000.0
            demanda = demanda_unidades[idx]
            factor = 1.0
            if demanda > disponible and demanda > 0:
                factor = disponible / demanda
            vendidas_unidades = demanda * factor
            inventario_final = max(0.0, disponible - vendidas_unidades)
            no_satisfecha = max(0.0, demanda - vendidas_unidades)

            ventas_miles = vendidas_unidades / 1000.0
            inventario_miles = inventario_final / 1000.0

            precio = marca["precio"]
            costo_transferencia = (
                marca["costo_unitario"]
                if marca["costo_unitario"] > 0
                else precio * self.MARGEN_TRANSFERENCIA
            )
            ingresos = precio * ventas_miles
            costo_productos = costo_transferencia * ventas_miles
            costo_inventario = (
                costo_transferencia * inventario_miles * self.COSTO_ALMACENAJE_PORC
            )
            publicidad = marca["publicidad"]
            costo_fuerza_ventas = (
                sum(marca["vendedores"].values()) * self.COSTO_VENDEDOR
            )
            contribucion = (
                ingresos - costo_productos - costo_inventario
                - publicidad - costo_fuerza_ventas
            )

            por_segmento = []
            for idx_seg, seg in enumerate(segmentos):
                ventas_seg = demanda_por_segmento[idx][idx_seg] * factor
                mercado_seg = mercado_total * (
                    max(0.0, float(seg.get("peso") or 0)) / peso_total
                )
                por_segmento.append({
                    "segmento_id": seg.get("id"),
                    "segmento_numero": seg.get("numero"),
                    "ventas_unidades": self._r(ventas_seg / 1000.0),
                    "porcion_mercado": self._r(
                        (ventas_seg / mercado_seg * 100.0) if mercado_seg > 0 else 0.0
                    ),
                })

            por_canal = self._repartir_canales(marca, canales, ventas_miles)

            resultados.append({
                "marca": marca["nombre"],
                "equipo_id": marca.get("equipo_id"),
                "tipo": marca.get("tipo", "SONITE"),
                "precio_final": self._r(precio),
                "precio_promedio": self._r(promedios["precio"]),
                "publicidad": self._r(publicidad),
                "investigacion": self._r(marca.get("investigacion", 0)),
                "produccion": self._r(marca["produccion"]),
                "inventario_inicial": self._r(marca["inventario"]),
                "unidades_vendidas": self._r(ventas_miles),
                "inventario": self._r(inventario_miles),
                "porcion_mercado": self._r(
                    (vendidas_unidades / mercado_total * 100.0) if mercado_total > 0 else 0.0
                ),
                "demanda_no_satisfecha": self._r(no_satisfecha / 1000.0),
                "ingresos": self._r(ingresos),
                "costo_transferencia": self._r(costo_transferencia),
                "costo_productos_vendidos": self._r(costo_productos),
                "costo_inventario": self._r(costo_inventario),
                "costo_fuerza_ventas": self._r(costo_fuerza_ventas),
                "contribucion_bruta_marketing": self._r(contribucion),
                "por_segmento": por_segmento,
                "por_canal": por_canal,
            })

        return {
            "resultados": resultados,
            "mercado_total": self._r(mercado_total),
            "anio": anio,
            "factor_mercado": self._r(mercado_total / self.mercado_base, 4),
        }

    # ------------------------------------------------------------------
    # Cálculos internos
    # ------------------------------------------------------------------
    def _calcular_mercado(self, anio):
        """Tamaño del mercado en unidades para el año indicado."""
        anios = max(0, int(anio) - self.anio_base)
        return self.mercado_base * ((1.0 + self.crecimiento_pib) ** anios)

    def _normalizar_marca(self, marca):
        vendedores = marca.get("vendedores") or {}
        if not isinstance(vendedores, dict):
            # Compatibilidad con llamadas antiguas: vendedores_canal1, ...
            vendedores = {
                1: marca.get("vendedores_canal1", 0),
                2: marca.get("vendedores_canal2", 0),
                3: marca.get("vendedores_canal3", 0),
            }
        detallistas = marca.get("detallistas") or {}
        if not isinstance(detallistas, dict):
            detallistas = {
                1: marca.get("detallistas_canal1", 0),
                2: marca.get("detallistas_canal2", 0),
                3: marca.get("detallistas_canal3", 0),
            }
        return {
            "nombre": str(marca.get("nombre") or marca.get("marca") or "?"),
            "equipo_id": marca.get("equipo_id"),
            "tipo": marca.get("tipo", "SONITE"),
            "precio": max(0.01, float(marca.get("precio") or 0.01)),
            "publicidad": max(0.0, float(marca.get("publicidad") or 0)),
            "investigacion": max(0.0, float(marca.get("investigacion") or 0)),
            "produccion": max(0.0, float(marca.get("produccion") or 0)),
            "inventario": max(0.0, float(marca.get("inventario") or 0)),
            "calidad": max(1.0, float(marca.get("calidad") or 50)),
            "costo_unitario": max(0.0, float(marca.get("costo_unitario") or 0)),
            "vendedores": {int(k): max(0.0, float(v or 0)) for k, v in vendedores.items()},
            "detallistas": {int(k): max(0.0, float(v or 0)) for k, v in detallistas.items()},
        }

    @staticmethod
    def _promedios(marcas):
        n = len(marcas)
        return {
            "precio": sum(m["precio"] for m in marcas) / n,
            "publicidad": sum(m["publicidad"] for m in marcas) / n,
            "calidad": sum(m["calidad"] for m in marcas) / n,
            "vendedores": sum(sum(m["vendedores"].values()) for m in marcas) / n,
            "detallistas": sum(sum(m["detallistas"].values()) for m in marcas) / n,
        }

    def _atractivo(self, marca, promedios, segmento, anio, idx_seg, idx_marca):
        """Atractivo de una marca dentro de un segmento."""
        ideal_x = float(segmento.get("valor_ideal_x") or 0)
        # Segmentos con ideal económico alto son más sensibles al precio.
        elasticidad = 1.2 + 0.6 * min(1.0, max(0.0, (ideal_x + 20.0) / 40.0))

        f_precio = (promedios["precio"] / marca["precio"]) ** elasticidad
        f_publicidad = self._factor_ratio(
            marca["publicidad"], promedios["publicidad"], 0.5, 0.25, 4.0
        )

        vendedores = sum(marca["vendedores"].values())
        detallistas = sum(marca["detallistas"].values())
        f_vendedores = self._factor_ratio(
            vendedores, promedios["vendedores"], 0.35, 0.4, 2.5
        )
        f_detallistas = self._factor_ratio(
            detallistas, promedios["detallistas"], 0.2, 0.5, 2.0
        )
        f_distribucion = f_vendedores * f_detallistas
        f_calidad = self._factor_ratio(
            marca["calidad"], promedios["calidad"], 0.4, 0.5, 2.0
        )

        ruido = self._ruido(anio, idx_seg, idx_marca)
        return max(1e-9, f_precio * f_publicidad * f_distribucion * f_calidad * ruido)

    @staticmethod
    def _factor_ratio(valor, promedio, exponente, minimo, maximo):
        if promedio <= 0:
            return 1.0
        factor = (max(0.0, valor) / promedio) ** exponente
        return min(maximo, max(minimo, factor))

    def _ruido(self, anio, idx_seg, idx_marca):
        """Ruido pseudoaleatorio reproducible (±6%)."""
        clave = f"{self.semilla}|{anio}|{idx_seg}|{idx_marca}"
        semilla = int(hashlib.sha256(clave.encode("utf-8")).hexdigest()[:16], 16)
        return random.Random(semilla).uniform(0.94, 1.06)

    def _repartir_canales(self, marca, canales, ventas_miles):
        """Reparte las ventas de la marca entre los canales disponibles."""
        pesos = []
        for canal in canales:
            canal_id = canal.get("id")
            total = max(1.0, float(canal.get("total_distribuidores") or 1))
            vendedores = marca["vendedores"].get(canal_id, 0.0)
            detallistas = marca["detallistas"].get(canal_id, 0.0)
            peso = vendedores + (detallistas / 100.0) + (total / 1000.0)
            pesos.append(max(0.0, peso))

        total_peso = sum(pesos)
        if total_peso <= 0:
            pesos = [1.0] * len(canales)
            total_peso = float(len(canales))

        resultado = []
        for canal, peso in zip(canales, pesos):
            canal_id = canal.get("id")
            resultado.append({
                "canal_id": canal_id,
                "canal_numero": canal.get("numero"),
                "vendedores": int(marca["vendedores"].get(canal_id, 0)),
                "detallistas": int(marca["detallistas"].get(canal_id, 0)),
                "ventas_unidades": self._r(ventas_miles * peso / total_peso),
            })
        return resultado

    @staticmethod
    def _r(valor, decimales=2):
        return round(float(valor), decimales)


def generar_eventos(anio, semilla="pacha"):
    """Genera eventos económicos deterministas del año.

    Se mantiene por compatibilidad; el motor actual no consume eventos.
    """
    eventos = {}
    eventos_fijos = {
        2: {"carnaval": True},
        5: {"crisis": True},
        8: {"navidad": True},
    }
    eventos.update(eventos_fijos.get(anio, {}))

    clave = f"{semilla}|evento|{anio}"
    import hashlib
    valor = int(hashlib.sha256(clave.encode("utf-8")).hexdigest()[:8], 16)
    if (valor % 100) < 20:
        eventos[["bloqueos", "navidad", "carnaval"][valor % 3]] = True
    return eventos
