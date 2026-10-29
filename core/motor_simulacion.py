"""
Motor de simulación — EL MUNDO DE MARKESTRAT BOLIVIA
===================================================

Motor propio y reproducible para la industria de helados en Bolivia. No
reproduce fórmulas de terceros: cada fórmula está escrita aquí y todos los
parámetros numéricos se leen de ``datos/escenario_bolivia.yaml`` a través de
``core/escenario.py``.

Unidades (consistentes en el motor y en los reportes)
-----------------------------------------------------
- ``mercado_total``, demanda y disponibilidad: **unidades físicas**.
- ``produccion``, ``inventario``, ``unidades_vendidas``: **miles de unidades**.
- ``precio``: Bs por unidad.
- ``publicidad``, ingresos, costos y contribución: **miles de Bs**.

Fórmulas
--------
1. Tamaño de mercado::

       mercado(año) = mercado_base * (1 + crecimiento_anual) ** (año - año_base)

   La inflación no altera el volumen: solo encarece costos y precios.

2. Atractivo de la marca *i* en el segmento *s*::

       A_ist = (P_ref,s / P_i) ** elasticidad_s
             * awareness_i ** respuesta_publicidad_s
             * cobertura_i ** peso_cobertura_s
             * f_producto_ist
             * ruido_ist

   - ``awareness_i = 1 - exp(-publicidad_i / escala_awareness)``
   - ``cobertura_i`` combina la presencia en puntos de venta y la fuerza de
     ventas propia, ponderada por la cobertura de cada canal.
   - ``f_producto = (1 - peso_calidad_s) + peso_calidad_s * ajuste_ist``.
     El ajuste compara los atributos del helado con el ideal del segmento
     (composición, porción, calidad, cremosidad y empaque).
   - ``ruido_ist`` es determinista (±4 %) y depende de la semilla, el año, el
     segmento y el nombre de la marca.

3. Reparto: la demanda de cada marca en cada segmento es
   ``mercado_segmento * A_ist / suma_j A_jst``.

4. Oferta: el inventario inicial se deteriora (merma anual); lo disponible es
   ``inventario_inicial * (1 - merma) + producción``. Si la demanda supera lo
   disponible, se vende todo lo disponible y el resto se registra como demanda
   no satisfecha. La demanda no satisfecha **no se arrastra** al año siguiente.

5. Canales: las ventas de la marca se reparten según su presencia relativa en
   cada canal (puntos de venta atendidos y vendedores).

6. Finanzas por marca (miles de Bs)::

       ingresos        = suma_c ventas_c * precio * (1 - margen_canal_c - logistica_c)
       costo_productos = costo_unitario * unidades_vendidas
       costo_inventario= costo_unitario * inventario_final * costo_almacenaje
       costo_fv        = vendedores_totales * costo_vendedor
       contribución    = ingresos - costo_productos - costo_inventario
                         - publicidad - costo_fv

   El costo de productos se calcula **solo sobre las unidades vendidas**: el
   inventario que queda se costea aparte con el costo de almacenaje.

7. Presupuesto del período siguiente::

       presupuesto = clamp(max(piso, contribución_neta * factor), piso, techo)

8. Cuotas: ``porcion_mercado`` usa como denominador el total vendido (suma
   100 %) y ``cobertura_mercado`` usa el mercado total del año.
"""
import hashlib
import random

from core import escenario as esc


class MotorSimulacion:
    """Motor de mercado de helados con 5 segmentos y 3 canales."""

    # Constantes expuestas para compatibilidad con los reportes de Año 0.
    _ESCENARIO = esc.cargar_escenario()
    _MOTOR = esc.parametros_motor(_ESCENARIO)

    MERCADO_BASE = esc.mercado_potencial(_ESCENARIO)
    COSTO_FIJO_POR_MARCA = float(_MOTOR["costo_fijo_por_marca"])
    COSTO_VENDEDOR = float(_MOTOR["costo_vendedor"])
    COSTO_ALMACENAJE_PORC = float(_MOTOR["costo_almacenaje"])
    MARGEN_TRANSFERENCIA = float(_MOTOR["margen_transferencia_defecto"])
    PRESUPUESTO_INICIAL = float(_MOTOR["presupuesto_inicial"])

    def __init__(self, config=None):
        """``config`` puede sobrescribir mercado, crecimiento, año y semilla.

        Claves reconocidas:
            - ``escenario``: dict ya cargado (por defecto el del repositorio)
            - ``mercado_total``: unidades físicas (por defecto el escenario)
            - ``crecimiento_anual`` o ``crecimiento_pib``: proporción anual
            - ``anio_base``: año de referencia del mercado (por defecto 0)
            - ``semilla``: texto del ruido determinista
            - ``inflacion_anual``: informativa; no altera el volumen
        """
        self.config = config or {}
        self.escenario = self.config.get("escenario") or self._ESCENARIO
        self.parametros = esc.parametros_motor(self.escenario)

        self.mercado_base = float(
            self.config.get("mercado_total")
            or esc.mercado_potencial(self.escenario)
        )
        self.crecimiento_anual = float(
            self.config.get(
                "crecimiento_anual",
                self.config.get(
                    "crecimiento_pib", esc.crecimiento_anual(self.escenario)
                ),
            )
        )
        self.inflacion_anual = float(self.config.get("inflacion_anual", 0.0))
        self.anio_base = int(self.config.get("anio_base", 0))
        self.semilla = str(
            self.config.get("semilla", self.parametros.get("semilla", "pacha"))
        )

    # ------------------------------------------------------------------
    # API principal
    # ------------------------------------------------------------------
    def simular_ronda(self, marcas_data, segmentos, canales, anio, industria_config=None):
        """Simula una ronda completa y devuelve resultados por marca."""
        marcas = [self._normalizar_marca(m) for m in (marcas_data or [])]
        mercado_total = self._calcular_mercado(anio)

        canales = [self._normalizar_canal(c) for c in (canales or [])]
        if not canales:
            canales = [{"id": None, "numero": 1, "nombre": "Canal único"}]

        # La cobertura depende de los canales: se calcula antes del atractivo.
        for marca in marcas:
            marca["pesos_canal"] = self._presencia_canales(marca, canales)

        if not marcas:
            return {
                "resultados": [],
                "mercado_total": self._r(mercado_total),
                "anio": anio,
                "factor_mercado": 1.0,
                "demanda_total": 0.0,
                "mercado_atendido": 0.0,
                "demanda_no_satisfecha_total": 0.0,
            }

        segmentos = [self._normalizar_segmento(s) for s in (segmentos or [])]
        if not segmentos:
            segmentos = [{
                "id": None, "numero": 1, "nombre": "Mercado completo",
                "peso": 1.0,
            }]

        promedios = self._promedios(marcas)
        n = len(marcas)
        demanda_unidades = [0.0] * n
        demanda_por_segmento = [[0.0] * len(segmentos) for _ in range(n)]

        # 1) Reparto del mercado por segmento.
        peso_total = sum(seg["peso"] for seg in segmentos)
        if peso_total <= 0:
            peso_total = float(len(segmentos))
            for seg in segmentos:
                seg["peso"] = 1.0

        for idx_seg, seg in enumerate(segmentos):
            mercado_seg = mercado_total * (seg["peso"] / peso_total)
            atractivos = [
                self._atractivo(m, promedios, seg, anio, idx_seg, idx)
                for idx, m in enumerate(marcas)
            ]
            total_atractivo = sum(atractivos)
            if total_atractivo <= 0:
                atractivos = [1.0] * n
                total_atractivo = float(n)

            for idx in range(n):
                demanda = mercado_seg * (atractivos[idx] / total_atractivo)
                demanda_unidades[idx] += demanda
                demanda_por_segmento[idx][idx_seg] = demanda

        # 2) Restricción de oferta, merma e inventario final.
        resultados = []
        vendidas_totales = 0.0
        demanda_total = 0.0
        no_satisfecha_total = 0.0

        for idx, marca in enumerate(marcas):
            merma = float(self.parametros.get("merma_anual_inventario", 0.0))
            disponible = max(
                0.0,
                marca["inventario"] * (1.0 - merma) + marca["produccion"],
            ) * 1000.0
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
            costo_unitario = marca["costo_unitario"]
            if costo_unitario <= 0:
                costo_unitario = precio * self.MARGEN_TRANSFERENCIA

            por_canal, ingresos, comision, logistica = self._repartir_canales(
                marca, canales, ventas_miles, precio
            )
            ingresos_brutos = precio * ventas_miles
            costo_productos = costo_unitario * ventas_miles
            costo_inventario = (
                costo_unitario * inventario_miles
                * float(self.parametros.get("costo_almacenaje", 0.0))
            )
            publicidad = marca["publicidad"]
            vendedores_totales = sum(marca["vendedores"].values())
            costo_fuerza_ventas = (
                vendedores_totales
                * float(self.parametros.get("costo_vendedor", 0.0))
            )
            contribucion = (
                ingresos - costo_productos - costo_inventario
                - publicidad - costo_fuerza_ventas
            )

            vendidas_totales += vendidas_unidades
            demanda_total += demanda
            no_satisfecha_total += no_satisfecha

            por_segmento = []
            for idx_seg, seg in enumerate(segmentos):
                ventas_seg = demanda_por_segmento[idx][idx_seg] * factor
                mercado_seg = mercado_total * (seg["peso"] / peso_total)
                por_segmento.append({
                    "segmento_id": seg.get("id"),
                    "segmento_numero": seg.get("numero"),
                    "ventas_unidades": self._r(ventas_seg / 1000.0),
                    "porcion_mercado": self._r(
                        (ventas_seg / mercado_seg * 100.0) if mercado_seg > 0 else 0.0
                    ),
                })

            resultados.append({
                "marca": marca["nombre"],
                "equipo_id": marca.get("equipo_id"),
                "tipo": marca.get("tipo", "HELADO"),
                "precio_final": self._r(precio),
                "precio_promedio": self._r(promedios["precio"]),
                "publicidad": self._r(publicidad),
                "investigacion": self._r(marca.get("investigacion", 0)),
                "produccion": self._r(marca["produccion"]),
                "inventario_inicial": self._r(marca["inventario"]),
                "unidades_vendidas": self._r(ventas_miles),
                "inventario": self._r(inventario_miles),
                "merma_unidades": self._r(
                    marca["inventario"] * merma
                ),
                "porcion_mercado": self._r(
                    (vendidas_unidades / vendidas_totales * 100.0)
                    if vendidas_totales > 0 else 0.0
                ),
                "cobertura_mercado": self._r(
                    (vendidas_unidades / mercado_total * 100.0)
                    if mercado_total > 0 else 0.0
                ),
                "demanda_no_satisfecha": self._r(no_satisfecha / 1000.0),
                "ingresos": self._r(ingresos),
                "ingresos_brutos": self._r(ingresos_brutos),
                "comision_canal": self._r(comision),
                "costo_logistico": self._r(logistica),
                "costo_transferencia": self._r(costo_unitario),
                "costo_productos_vendidos": self._r(costo_productos),
                "costo_inventario": self._r(costo_inventario),
                "costo_fuerza_ventas": self._r(costo_fuerza_ventas),
                "contribucion_bruta_marketing": self._r(contribucion),
                "awareness": self._r(marca["awareness"], 4),
                "cobertura": self._r(marca["cobertura"], 4),
                "por_segmento": por_segmento,
                "por_canal": por_canal,
            })

        # La cuota de mercado se recalcula con el total vendido ya conocido.
        if vendidas_totales > 0:
            for resultado in resultados:
                resultado["porcion_mercado"] = self._r(
                    resultado["unidades_vendidas"] * 1000.0
                    / vendidas_totales * 100.0
                )
            # Ajuste de redondeo: la última marca absorbe el residuo para que
            # las cuotas sumen exactamente 100,00 %.
            residuo = self._r(
                100.0 - sum(r["porcion_mercado"] for r in resultados)
            )
            if resultados and abs(residuo) > 0:
                resultados[-1]["porcion_mercado"] = self._r(
                    resultados[-1]["porcion_mercado"] + residuo
                )

        return {
            "resultados": resultados,
            "mercado_total": self._r(mercado_total),
            "anio": anio,
            "factor_mercado": self._r(mercado_total / self.mercado_base, 4),
            "demanda_total": self._r(demanda_total / 1000.0),
            "mercado_atendido": self._r(vendidas_totales / 1000.0),
            "demanda_no_satisfecha_total": self._r(no_satisfecha_total / 1000.0),
        }

    # ------------------------------------------------------------------
    # Presupuesto
    # ------------------------------------------------------------------
    def calcular_presupuesto(self, contribucion_neta):
        """Presupuesto del período siguiente, acotado al rango del escenario."""
        piso = float(self.parametros.get("presupuesto_piso", 0.0))
        techo = float(self.parametros.get("presupuesto_techo", float("inf")))
        factor = float(self.parametros.get("presupuesto_factor_contribucion", 0.30))
        valor = max(piso, float(contribucion_neta) * factor)
        return round(min(techo, valor), 2)

    # ------------------------------------------------------------------
    # Cálculos internos
    # ------------------------------------------------------------------
    def _calcular_mercado(self, anio):
        """Tamaño del mercado en unidades para el año indicado."""
        anios = max(0, int(anio) - self.anio_base)
        return self.mercado_base * ((1.0 + self.crecimiento_anual) ** anios)

    def _normalizar_marca(self, marca):
        vendedores = marca.get("vendedores") or {}
        if not isinstance(vendedores, dict):
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

        publicidad = max(0.0, float(marca.get("publicidad") or 0))
        escala = max(1.0, float(self.parametros.get("escala_awareness", 2000.0)))
        awareness = 1.0 - pow(2.718281828459045, -publicidad / escala)

        return {
            "nombre": str(marca.get("nombre") or marca.get("marca") or "?"),
            "equipo_id": marca.get("equipo_id"),
            "tipo": marca.get("tipo", "HELADO"),
            "precio": max(0.01, float(marca.get("precio") or 0.01)),
            "publicidad": publicidad,
            "investigacion": max(0.0, float(marca.get("investigacion") or 0)),
            "produccion": max(0.0, float(marca.get("produccion") or 0)),
            "inventario": max(0.0, float(marca.get("inventario") or 0)),
            "calidad": max(1.0, float(marca.get("calidad") or 50)),
            "costo_unitario": max(0.0, float(marca.get("costo_unitario") or 0)),
            "atributos": self._atributos_marca(marca),
            "vendedores": {int(k): max(0.0, float(v or 0)) for k, v in vendedores.items()},
            "detallistas": {int(k): max(0.0, float(v or 0)) for k, v in detallistas.items()},
            "awareness": min(1.0, max(0.0, awareness)),
        }

    def _atributos_marca(self, marca):
        """Atributos 1-5 de la marca; si faltan, usa el producto de referencia."""
        iniciales = self.escenario["atributos_iniciales"]
        atributos = marca.get("atributos")
        if isinstance(atributos, (list, tuple)) and atributos:
            base = {i + 1: float(v or 0) for i, v in enumerate(atributos)}
        elif isinstance(atributos, dict):
            base = {int(k): float(v or 0) for k, v in atributos.items()}
        else:
            base = dict(iniciales)

        # Si la marca solo trae el índice de calidad, se usa como calidad de
        # ingredientes para no perder la información del estado de la marca.
        if "atributos" not in marca and marca.get("calidad") is not None:
            base[3] = float(marca.get("calidad") or base.get(3, 60))
        return base

    def _normalizar_segmento(self, segmento):
        """Completa el segmento con los parámetros del escenario por número."""
        numero = int(segmento.get("numero") or 0)
        referencia = {}
        for candidato in self.escenario["segmentos"]:
            if int(candidato["numero"]) == numero:
                referencia = candidato
                break
        if not referencia:
            referencia = self.escenario["segmentos"][0]

        base = {
            "id": segmento.get("id"),
            "numero": numero or int(referencia["numero"]),
            "nombre": segmento.get("nombre") or referencia["nombre"],
            "peso": max(0.0, float(segmento.get("peso") or 0.0)),
            "elasticidad_precio": float(
                segmento.get("elasticidad_precio", referencia["elasticidad_precio"])
            ),
            "respuesta_publicidad": float(
                segmento.get("respuesta_publicidad", referencia["respuesta_publicidad"])
            ),
            "peso_cobertura": float(
                segmento.get("peso_cobertura", referencia["peso_cobertura"])
            ),
            "peso_calidad": float(
                segmento.get("peso_calidad", referencia["peso_calidad"])
            ),
            "preferencia_composicion": segmento.get(
                "preferencia_composicion", referencia["preferencia_composicion"]
            ),
            "ideal_porcion_ml": float(
                segmento.get("ideal_porcion_ml", referencia["ideal_porcion_ml"])
            ),
            "ideal_calidad": float(
                segmento.get("ideal_calidad", referencia["ideal_calidad"])
            ),
            "ideal_cremosidad": float(
                segmento.get("ideal_cremosidad", referencia["ideal_cremosidad"])
            ),
            "ideal_empaque": float(
                segmento.get("ideal_empaque", referencia["ideal_empaque"])
            ),
            "sensibilidad_porcion": float(
                segmento.get("sensibilidad_porcion", referencia["sensibilidad_porcion"])
            ),
        }
        if base["peso"] <= 0:
            base["peso"] = float(referencia["peso"])
        return base

    def _normalizar_canal(self, canal):
        """Completa el canal con los parámetros del escenario por número."""
        numero = int(canal.get("numero") or 0)
        referencia = {}
        for candidato in self.escenario["canales"]:
            if int(candidato["numero"]) == numero:
                referencia = candidato
                break
        if not referencia:
            referencia = self.escenario["canales"][0]

        puntos = canal.get("puntos_de_venta") or canal.get("total_distribuidores")
        if not puntos:
            puntos = referencia["puntos_de_venta"]
        return {
            "id": canal.get("id"),
            "numero": numero or int(referencia["numero"]),
            "nombre": canal.get("nombre") or referencia["nombre"],
            "cobertura": float(canal.get("cobertura", referencia["cobertura"])),
            "margen_canal": float(
                canal.get("margen_canal", referencia["margen_canal"])
            ),
            "costo_logistico": float(
                canal.get("costo_logistico", referencia["costo_logistico"])
            ),
            "puntos_de_venta": max(1.0, float(puntos)),
            "exigencia_calidad": float(
                canal.get("exigencia_calidad", referencia["exigencia_calidad"])
            ),
        }

    @staticmethod
    def _promedios(marcas):
        n = len(marcas) or 1
        return {
            "precio": sum(m["precio"] for m in marcas) / n,
            "publicidad": sum(m["publicidad"] for m in marcas) / n,
            "calidad": sum(m["calidad"] for m in marcas) / n,
        }

    def _atractivo(self, marca, promedios, segmento, anio, idx_seg, idx_marca):
        """Atractivo de una marca dentro de un segmento."""
        f_precio = (
            max(1e-6, promedios["precio"]) / marca["precio"]
        ) ** segmento["elasticidad_precio"]

        f_publicidad = max(1e-6, marca["awareness"]) ** segmento["respuesta_publicidad"]

        cobertura = max(
            float(self.parametros.get("cobertura_minima", 0.02)),
            marca["cobertura"],
        )
        f_cobertura = cobertura ** segmento["peso_cobertura"]

        ajuste = self._ajuste_producto(marca, segmento)
        gamma = min(1.0, max(0.0, segmento["peso_calidad"]))
        f_producto = (1.0 - gamma) + gamma * ajuste

        ruido = self._ruido(anio, idx_seg, marca["nombre"], marca.get("equipo_id"))
        return max(1e-12, f_precio * f_publicidad * f_cobertura * f_producto * ruido)

    def _ajuste_producto(self, marca, segmento):
        """Ajuste 0-1 entre los atributos del helado y el ideal del segmento."""
        atributos = marca["atributos"]

        composicion = int(round(float(atributos.get(1, 1) or 0)))
        composicion = min(2, max(0, composicion))
        clave = ("agua", "mixto", "crema")[composicion]
        fit_composicion = float(
            (segmento["preferencia_composicion"] or {}).get(clave, 0.0)
        )

        porcion = float(atributos.get(2, 120) or 120)
        rango = 250.0 - 60.0
        fit_porcion = 1.0 - abs(porcion - segmento["ideal_porcion_ml"]) / rango
        fit_porcion = min(1.0, max(0.0, fit_porcion))

        fit_calidad = self._gaussiana(
            float(atributos.get(3, 60) or 60),
            segmento["ideal_calidad"],
            float(self.parametros.get("sigma_calidad", 22.0)),
        )
        fit_cremosidad = self._gaussiana(
            float(atributos.get(4, 60) or 60),
            segmento["ideal_cremosidad"],
            float(self.parametros.get("sigma_cremosidad", 25.0)),
        )
        fit_empaque = self._gaussiana(
            float(atributos.get(5, 60) or 60),
            segmento["ideal_empaque"],
            float(self.parametros.get("sigma_empaque", 30.0)),
        )

        pesos = {
            "composicion": 0.30,
            "porcion": 0.15 + 0.15 * segmento["sensibilidad_porcion"],
            "calidad": 0.25,
            "cremosidad": 0.20,
            "empaque": 0.10,
        }
        suma = sum(pesos.values())
        return (
            fit_composicion * pesos["composicion"]
            + fit_porcion * pesos["porcion"]
            + fit_calidad * pesos["calidad"]
            + fit_cremosidad * pesos["cremosidad"]
            + fit_empaque * pesos["empaque"]
        ) / suma

    @staticmethod
    def _gaussiana(valor, ideal, sigma):
        """Campana 0-1 centrada en el ideal del segmento."""
        if sigma <= 0:
            return 1.0 if abs(valor - ideal) < 1e-9 else 0.0
        return pow(2.718281828459045, -((valor - ideal) ** 2) / (2.0 * sigma * sigma))

    @staticmethod
    def _factor_ratio(valor, promedio, exponente, minimo, maximo):
        """Compatibilidad: factor de razón acotado entre ``minimo`` y ``maximo``."""
        if promedio <= 0:
            return 1.0
        factor = (max(0.0, valor) / promedio) ** exponente
        return min(maximo, max(minimo, factor))

    def _ruido(self, anio, idx_seg, nombre, equipo_id=None):
        """Ruido pseudoaleatorio reproducible."""
        minimo = float(self.parametros.get("ruido_minimo", 0.96))
        maximo = float(self.parametros.get("ruido_maximo", 1.04))
        clave = f"{self.semilla}|{anio}|{idx_seg}|{equipo_id}|{nombre}"
        semilla = int(hashlib.sha256(clave.encode("utf-8")).hexdigest()[:16], 16)
        return random.Random(semilla).uniform(minimo, maximo)

    def _presencia_canales(self, marca, canales):
        """Presencia de la marca en cada canal y cobertura global.

        ``presencia_ic = peso_pdv * min(1, detallistas_ic / puntos_c)
                          + peso_fv * min(1, vendedores_ic / vendedores_plenos)``
        es la fracción de puntos que la marca alcanza en ese canal (0-1).

        La **cobertura global** es la suma absoluta ``Σ cobertura_c * presencia_ic``
        (0-1): una marca con poca presencia queda con cobertura baja aunque el
        reparto interno de sus ventas se normalice. El reparto de ventas entre
        canales usa la presencia ponderada normalizada (suma 1).
        """
        peso_detallistas = float(self.parametros.get("peso_detallistas", 0.60))
        peso_vendedores = float(self.parametros.get("peso_vendedores", 0.40))
        vendedores_plenos = max(
            1.0, float(self.parametros.get("vendedores_plenos", 20))
        )

        presencias = []
        for canal in canales:
            canal_id = canal.get("id")
            detallistas = marca["detallistas"].get(canal_id, 0.0)
            vendedores = marca["vendedores"].get(canal_id, 0.0)
            presencia_pdv = min(1.0, detallistas / canal["puntos_de_venta"])
            presencia_fv = min(1.0, vendedores / vendedores_plenos)
            presencia = (
                peso_detallistas * presencia_pdv + peso_vendedores * presencia_fv
            )
            presencias.append(max(0.0, presencia))

        cobertura = sum(
            c["cobertura"] * p for c, p in zip(canales, presencias)
        )
        marca["cobertura"] = min(
            float(self.parametros.get("cobertura_maxima", 1.0)),
            max(float(self.parametros.get("cobertura_minima", 0.02)), cobertura),
        )

        pesos = [c["cobertura"] * p for c, p in zip(canales, presencias)]
        total = sum(pesos)
        if total <= 0:
            return [1.0 / len(canales)] * len(canales)
        return [p / total for p in pesos]

    def _repartir_canales(self, marca, canales, ventas_miles, precio):
        """Reparte las ventas entre canales y calcula ingresos netos.

        Devuelve ``(por_canal, ingresos, comision, logistica)`` en miles de Bs.
        """
        pesos = marca.get("pesos_canal") or self._presencia_canales(marca, canales)

        resultado = []
        ingresos = 0.0
        comision = 0.0
        logistica = 0.0
        acumulado = 0.0
        for indice, (canal, peso) in enumerate(zip(canales, pesos)):
            if indice == len(canales) - 1:
                ventas_canal = round(ventas_miles - acumulado, 6)
            else:
                ventas_canal = round(ventas_miles * peso, 6)
                acumulado += ventas_canal
            ventas_canal = max(0.0, ventas_canal)

            margen = canal["margen_canal"]
            logistico = canal["costo_logistico"]
            ingreso_neto = ventas_canal * precio * (1.0 - margen - logistico)
            ingresos += ingreso_neto
            comision += ventas_canal * precio * margen
            logistica += ventas_canal * precio * logistico

            resultado.append({
                "canal_id": canal.get("id"),
                "canal_numero": canal.get("numero"),
                "vendedores": int(marca["vendedores"].get(canal.get("id"), 0)),
                "detallistas": int(marca["detallistas"].get(canal.get("id"), 0)),
                "margen_canal": self._r(margen, 4),
                "ventas_unidades": self._r(ventas_canal),
                "ingresos": self._r(ingreso_neto),
            })

        return resultado, ingresos, comision, logistica

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
    valor = int(hashlib.sha256(clave.encode("utf-8")).hexdigest()[:8], 16)
    if (valor % 100) < 20:
        eventos[["bloqueos", "navidad", "carnaval"][valor % 3]] = True
    return eventos
