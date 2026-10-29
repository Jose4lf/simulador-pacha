"""
Pruebas del motor de helados (Fase 2).

Verifican las fórmulas documentadas en ``core/motor_simulacion.py`` usando el
escenario real de ``datos/escenario_bolivia.yaml``. No tocan la base de datos.

Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import unittest

from core import escenario as esc
from core.motor_simulacion import MotorSimulacion

ESCENARIO = esc.cargar_escenario()
CATALOGO = esc.cargar_catalogo()
MERCADO = esc.mercado_potencial(ESCENARIO)

SEGMENTOS = [
    {"id": s["numero"], "numero": s["numero"], "peso": s["peso"]}
    for s in ESCENARIO["segmentos"]
]
CANALES = [
    {
        "id": c["numero"], "numero": c["numero"],
        "puntos_de_venta": c["puntos_de_venta"],
    }
    for c in ESCENARIO["canales"]
]

ATRIBUTOS_AGUA = {1: 0, 2: 90, 3: 45, 4: 25, 5: 45}
ATRIBUTOS_MIXTO = {1: 1, 2: 120, 3: 62, 4: 55, 5: 60}
ATRIBUTOS_CREMA = {1: 2, 2: 140, 3: 75, 4: 78, 5: 70}


def marca(nombre, precio=7.0, publicidad=1200, produccion=60000, inventario=0,
          atributos=None, equipo_id=1, vendedores=None, detallistas=None,
          costo_unitario=None):
    atributos = dict(atributos or ATRIBUTOS_MIXTO)
    atributos[6] = (
        esc.costo_estandar(atributos, ESCENARIO)
        if costo_unitario is None else costo_unitario
    )
    return {
        "nombre": nombre,
        "equipo_id": equipo_id,
        "tipo": "HELADO",
        "precio": precio,
        "publicidad": publicidad,
        "produccion": produccion,
        "inventario": inventario,
        "atributos": atributos,
        "costo_unitario": atributos[6],
        "vendedores": vendedores or {1: 6, 2: 12, 3: 4},
        "detallistas": detallistas or {1: 9000, 2: 650, 3: 900},
    }


def motor(**extra):
    return MotorSimulacion(extra)


def correr(marcas, anio=1, **extra):
    return motor(**extra).simular_ronda(marcas, SEGMENTOS, CANALES, anio)


def por_nombre(salida, nombre):
    return next(r for r in salida["resultados"] if r["marca"] == nombre)


class TestMercado(unittest.TestCase):
    def test_mercado_base_del_escenario(self):
        self.assertAlmostEqual(motor()._calcular_mercado(0), MERCADO, places=2)

    def test_mercado_crece_con_el_crecimiento_anual(self):
        crecimiento = esc.crecimiento_anual(ESCENARIO)
        self.assertAlmostEqual(
            motor()._calcular_mercado(2),
            MERCADO * (1 + crecimiento) ** 2,
            places=2,
        )

    def test_mercado_en_el_anio_diez(self):
        salida = correr([marca("AAA")], anio=10)
        esperado = MERCADO * (1 + esc.crecimiento_anual(ESCENARIO)) ** 10
        self.assertAlmostEqual(salida["mercado_total"], esperado, places=0)

    def test_config_sobrescribe_el_mercado(self):
        salida = correr([marca("AAA")], mercado_total=1_000_000, crecimiento_anual=0.0)
        self.assertAlmostEqual(salida["mercado_total"], 1_000_000, places=0)

    def test_sin_marcas_devuelve_estructura_vacia(self):
        salida = motor().simular_ronda([], SEGMENTOS, CANALES, 1)
        self.assertEqual(salida["resultados"], [])
        self.assertAlmostEqual(salida["mercado_total"], MERCADO * 1.02, places=0)


class TestReparto(unittest.TestCase):
    def test_reproducible(self):
        marcas = [marca("AAA"), marca("BBB", precio=8.5)]
        self.assertEqual(correr(marcas), correr(marcas))

    def test_reparte_todo_el_mercado_si_hay_oferta(self):
        marcas = [marca(f"M{i}", produccion=20000) for i in range(4)]
        salida = correr(marcas)
        vendidas = sum(r["unidades_vendidas"] for r in salida["resultados"]) * 1000
        # Las ventas se redondean a centésimas de miles de unidades: el residuo
        # máximo por marca es de 10 unidades.
        self.assertAlmostEqual(vendidas, salida["mercado_total"], delta=20.0)
        for resultado in salida["resultados"]:
            self.assertEqual(resultado["demanda_no_satisfecha"], 0)

    def test_cuotas_suman_cien(self):
        marcas = [marca(f"M{i}", precio=6 + i * 0.5, produccion=20000) for i in range(6)]
        salida = correr(marcas)
        total = sum(r["porcion_mercado"] for r in salida["resultados"])
        self.assertAlmostEqual(total, 100.0, places=2)

    def test_marcas_iguales_se_ajustan_por_ruido(self):
        marcas = [marca(f"M{i}", produccion=20000) for i in range(4)]
        salida = correr(marcas)
        cuotas = [r["porcion_mercado"] for r in salida["resultados"]]
        self.assertTrue(all(20.0 < c < 30.0 for c in cuotas), cuotas)


class TestAtributosDelProducto(unittest.TestCase):
    def test_agua_prefiere_segmento_de_barrio(self):
        marcas = [
            marca("AGUA", atributos=ATRIBUTOS_AGUA),
            marca("CREMA", atributos=ATRIBUTOS_CREMA),
        ]
        salida = correr(marcas)
        agua = por_nombre(salida, "AGUA")
        barrio = next(
            s for s in agua["por_segmento"] if s["segmento_numero"] == 5
        )
        gourmet = next(
            s for s in agua["por_segmento"] if s["segmento_numero"] == 4
        )
        self.assertGreater(barrio["porcion_mercado"], gourmet["porcion_mercado"])

    def test_crema_prefiere_hogares_gourmet(self):
        marcas = [
            marca("AGUA", atributos=ATRIBUTOS_AGUA),
            marca("CREMA", atributos=ATRIBUTOS_CREMA),
        ]
        salida = correr(marcas)
        crema = por_nombre(salida, "CREMA")
        barrio = next(
            s for s in crema["por_segmento"] if s["segmento_numero"] == 5
        )
        gourmet = next(
            s for s in crema["por_segmento"] if s["segmento_numero"] == 4
        )
        self.assertGreater(gourmet["porcion_mercado"], barrio["porcion_mercado"])

    def test_calidad_se_ajusta_al_ideal_del_segmento(self):
        """La calidad no es "más es mejor": cada segmento tiene su ideal."""
        baja = dict(ATRIBUTOS_CREMA)
        baja[3] = 40
        alta = dict(ATRIBUTOS_CREMA)
        alta[3] = 90
        salida = correr([marca("BAJA", atributos=baja), marca("ALTA", atributos=alta)])

        def cuota(nombre, segmento):
            resultado = por_nombre(salida, nombre)
            return next(
                s["porcion_mercado"]
                for s in resultado["por_segmento"]
                if s["segmento_numero"] == segmento
            )

        # Hogares gourmet (ideal 88) prefieren la calidad alta; el comprador de
        # barrio (ideal 45) prefiere la calidad baja.
        self.assertGreater(cuota("ALTA", 4), cuota("BAJA", 4))
        self.assertGreater(cuota("BAJA", 5), cuota("ALTA", 5))

    def test_costo_unitario_sube_con_los_atributos(self):
        baja = dict(ATRIBUTOS_CREMA)
        baja[3] = 40
        alta = dict(ATRIBUTOS_CREMA)
        alta[3] = 90
        salida = correr([marca("BAJA", atributos=baja), marca("ALTA", atributos=alta)])
        self.assertGreater(
            por_nombre(salida, "ALTA")["costo_transferencia"],
            por_nombre(salida, "BAJA")["costo_transferencia"],
        )

    def test_costo_unitario_sale_del_escenario(self):
        marcas = [marca("AAA")]
        salida = correr(marcas)
        esperado = esc.costo_estandar(ATRIBUTOS_MIXTO, ESCENARIO)
        self.assertAlmostEqual(salida["resultados"][0]["costo_transferencia"], esperado)


class TestPrecioPublicidadCobertura(unittest.TestCase):
    def test_precio_menor_gana_cuota(self):
        salida = correr([
            marca("CARO", precio=12.0, produccion=60000),
            marca("BARATO", precio=5.0, produccion=60000),
        ])
        self.assertGreater(
            por_nombre(salida, "BARATO")["porcion_mercado"],
            por_nombre(salida, "CARO")["porcion_mercado"],
        )

    def test_mas_publicidad_gana_cuota(self):
        salida = correr([
            marca("MUDO", publicidad=200, produccion=60000),
            marca("FUERTE", publicidad=6000, produccion=60000),
        ])
        self.assertGreater(
            por_nombre(salida, "FUERTE")["porcion_mercado"],
            por_nombre(salida, "MUDO")["porcion_mercado"],
        )

    def test_mas_cobertura_gana_cuota(self):
        salida = correr([
            marca("CORTO", detallistas={1: 500, 2: 10, 3: 10},
                  vendedores={1: 1, 2: 1, 3: 1}, produccion=60000),
            marca("LARGO", detallistas={1: 90000, 2: 1400, 3: 6500},
                  vendedores={1: 20, 2: 20, 3: 20}, produccion=60000),
        ])
        self.assertGreater(
            por_nombre(salida, "LARGO")["porcion_mercado"],
            por_nombre(salida, "CORTO")["porcion_mercado"],
        )
        self.assertLessEqual(por_nombre(salida, "LARGO")["cobertura"], 1.0)
        self.assertGreaterEqual(por_nombre(salida, "CORTO")["cobertura"], 0.02)

    def test_awareness_crece_con_la_publicidad(self):
        salida = correr([
            marca("MUDO", publicidad=0, produccion=20000),
            marca("FUERTE", publicidad=6000, produccion=20000),
        ])
        self.assertLess(por_nombre(salida, "MUDO")["awareness"], 0.05)
        self.assertGreater(por_nombre(salida, "FUERTE")["awareness"], 0.9)


class TestOfertaEInventario(unittest.TestCase):
    def test_limita_por_produccion_y_reporta_no_satisfecha(self):
        salida = correr([marca("AAA", produccion=500)])
        resultado = salida["resultados"][0]
        self.assertAlmostEqual(resultado["unidades_vendidas"], 500, places=2)
        self.assertEqual(resultado["inventario"], 0)
        self.assertGreater(resultado["demanda_no_satisfecha"], 0)
        self.assertGreater(salida["demanda_no_satisfecha_total"], 0)

    def test_inventario_se_deteriora_por_merma(self):
        merma = float(ESCENARIO["motor"]["merma_anual_inventario"])
        salida = correr([
            marca("AAA", produccion=0, inventario=1000),
            marca("BBB", produccion=50000),
        ])
        aaa = por_nombre(salida, "AAA")
        disponible = 1000 * (1 - merma)
        self.assertAlmostEqual(
            aaa["unidades_vendidas"] + aaa["inventario"], disponible, places=1
        )
        self.assertAlmostEqual(aaa["merma_unidades"], 1000 * merma, places=2)

    def test_cogs_solo_sobre_unidades_vendidas(self):
        # Produce más que el mercado entero: una parte queda en inventario.
        salida = correr([marca("AAA", produccion=70000)])
        resultado = salida["resultados"][0]
        esperado = resultado["costo_transferencia"] * resultado["unidades_vendidas"]
        self.assertAlmostEqual(
            resultado["costo_productos_vendidos"], esperado, places=1
        )
        self.assertGreater(resultado["inventario"], 0)
        self.assertGreater(resultado["costo_inventario"], 0)
        self.assertLess(
            resultado["costo_productos_vendidos"],
            resultado["costo_transferencia"] * 70000,
        )

    def test_inventario_final_no_se_vende_dos_veces(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        self.assertAlmostEqual(
            resultado["produccion"],
            resultado["unidades_vendidas"] + resultado["inventario"],
            places=2,
        )


class TestFinanzas(unittest.TestCase):
    def test_ingresos_descuentan_margen_y_logistica(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        self.assertLess(resultado["ingresos"], resultado["ingresos_brutos"])
        self.assertGreater(resultado["comision_canal"], 0)
        self.assertGreater(resultado["costo_logistico"], 0)
        self.assertAlmostEqual(
            resultado["ingresos"]
            + resultado["comision_canal"]
            + resultado["costo_logistico"],
            resultado["ingresos_brutos"],
            places=1,
        )

    def test_contribucion_descuenta_publicidad_y_fuerza_ventas(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        esperado = (
            resultado["ingresos"]
            - resultado["costo_productos_vendidos"]
            - resultado["costo_inventario"]
            - resultado["publicidad"]
            - resultado["costo_fuerza_ventas"]
        )
        self.assertAlmostEqual(
            resultado["contribucion_bruta_marketing"], esperado, places=1
        )

    def test_costo_fuerza_ventas_usa_los_vendedores(self):
        salida = correr([
            marca("AAA", vendedores={1: 10, 2: 10, 3: 10}, produccion=20000)
        ])
        resultado = salida["resultados"][0]
        self.assertAlmostEqual(
            resultado["costo_fuerza_ventas"],
            30 * float(ESCENARIO["motor"]["costo_vendedor"]),
            places=2,
        )

    def test_presupuesto_respeta_el_piso(self):
        self.assertAlmostEqual(
            motor().calcular_presupuesto(1000),
            float(ESCENARIO["motor"]["presupuesto_piso"]),
            places=2,
        )

    def test_presupuesto_respeta_el_techo(self):
        self.assertAlmostEqual(
            motor().calcular_presupuesto(10_000_000),
            float(ESCENARIO["motor"]["presupuesto_techo"]),
            places=2,
        )

    def test_presupuesto_proporcional_a_la_contribucion(self):
        # Por encima del piso, el presupuesto es contribución * factor.
        factor = float(ESCENARIO["motor"]["presupuesto_factor_contribucion"])
        piso = float(ESCENARIO["motor"]["presupuesto_piso"])
        contribucion = piso / factor + 1000.0
        self.assertAlmostEqual(
            motor().calcular_presupuesto(contribucion),
            contribucion * factor,
            places=2,
        )


class TestCanalesYSegmentos(unittest.TestCase):
    def test_ventas_por_canal_suman_las_vendidas(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        self.assertEqual(len(resultado["por_canal"]), 3)
        self.assertAlmostEqual(
            sum(c["ventas_unidades"] for c in resultado["por_canal"]),
            resultado["unidades_vendidas"],
            delta=0.05,
        )

    def test_ventas_por_segmento_suman_las_vendidas(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        self.assertEqual(len(resultado["por_segmento"]), 5)
        self.assertAlmostEqual(
            sum(s["ventas_unidades"] for s in resultado["por_segmento"]),
            resultado["unidades_vendidas"],
            delta=0.05,
        )

    def test_el_mercado_se_reparte_entre_los_cinco_segmentos(self):
        salida = correr([marca("AAA", produccion=20000)])
        resultado = salida["resultados"][0]
        total = sum(s["ventas_unidades"] for s in resultado["por_segmento"])
        for segmento in resultado["por_segmento"]:
            self.assertGreater(segmento["ventas_unidades"], 0)
        self.assertAlmostEqual(total, resultado["unidades_vendidas"], delta=0.05)

    def test_canal_con_mas_presencia_recibe_mas_ventas(self):
        salida = correr([
            marca("AAA", detallistas={1: 90000, 2: 10, 3: 10},
                  vendedores={1: 20, 2: 1, 3: 1}, produccion=20000)
        ])
        canales = salida["resultados"][0]["por_canal"]
        self.assertEqual(max(canales, key=lambda c: c["ventas_unidades"])["canal_numero"], 1)


class TestRuido(unittest.TestCase):
    def test_ruido_dentro_del_rango(self):
        parametros = ESCENARIO["motor"]
        minimo = float(parametros["ruido_minimo"])
        maximo = float(parametros["ruido_maximo"])
        motor_ = motor()
        for anio in range(0, 11):
            for segmento in range(5):
                valor = motor_._ruido(anio, segmento, "Aurora", 1)
                self.assertGreaterEqual(valor, minimo)
                self.assertLessEqual(valor, maximo)

    def test_ruido_cambia_entre_marcas(self):
        motor_ = motor()
        self.assertNotEqual(
            motor_._ruido(1, 0, "Aurora", 1),
            motor_._ruido(1, 0, "Bruma", 1),
        )

    def test_semilla_distinta_cambia_el_reparto(self):
        marcas = [marca(f"M{i}", produccion=20000) for i in range(4)]
        a = correr(marcas, semilla="uno")
        b = correr(marcas, semilla="dos")
        cuotas_a = [r["porcion_mercado"] for r in a["resultados"]]
        cuotas_b = [r["porcion_mercado"] for r in b["resultados"]]
        self.assertNotEqual(cuotas_a, cuotas_b)


class TestCatalogoCompleto(unittest.TestCase):
    """Diez marcas del catálogo contra el mercado completo."""

    def setUp(self):
        produccion = {"agua": 9000, "mixto": 6000, "crema": 4200}
        self.marcas = []
        for indice, entrada in enumerate(CATALOGO["marcas"], start=1):
            linea = CATALOGO["lineas"][entrada["linea"]]
            atributos = {
                1: linea["composicion"], 2: linea["porcion_ml"],
                3: linea["calidad_ingredientes"], 4: linea["cremosidad"],
                5: linea["empaque"],
            }
            self.marcas.append(marca(
                entrada["nombre"], precio=linea["precio_inicial"],
                produccion=produccion[entrada["linea"]], inventario=300,
                atributos=atributos, equipo_id=(indice - 1) // 2 + 1,
            ))

    def test_no_queda_demanda_insatisfecha_en_el_arranque(self):
        salida = correr(self.marcas)
        self.assertEqual(salida["demanda_no_satisfecha_total"], 0)

    def test_todas_las_marcas_son_rentables(self):
        salida = correr(self.marcas)
        for resultado in salida["resultados"]:
            self.assertGreater(resultado["contribucion_bruta_marketing"], 0)

    def test_las_tres_lineas_tienen_participacion(self):
        salida = correr(self.marcas)
        por_linea = {}
        for entrada, resultado in zip(CATALOGO["marcas"], salida["resultados"]):
            por_linea[entrada["linea"]] = (
                por_linea.get(entrada["linea"], 0.0) + resultado["porcion_mercado"]
            )
        for linea, cuota in por_linea.items():
            self.assertGreater(cuota, 15.0, f"{linea} tiene solo {cuota:.1f}%")

    def test_cuotas_suman_cien(self):
        salida = correr(self.marcas)
        self.assertAlmostEqual(
            sum(r["porcion_mercado"] for r in salida["resultados"]), 100.0, places=2
        )


if __name__ == "__main__":
    unittest.main()
