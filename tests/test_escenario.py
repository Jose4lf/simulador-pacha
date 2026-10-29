"""
Pruebas del escenario «El Mundo de Markestrat Bolivia» (Fase 1).

Verifican que los datos del YAML cumplan las reglas del simulador y que el
cargador rechace configuraciones inválidas. No tocan la base de datos.

Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import copy
import unittest

from core import escenario as esc


class TestCargaEscenario(unittest.TestCase):
    def setUp(self):
        self.datos = esc.cargar_escenario(recargar=True)

    def test_codigo_e_identidad(self):
        self.assertEqual(self.datos["meta"]["codigo"], "mundo_markestrat_bolivia")
        self.assertEqual(self.datos["meta"]["moneda"], "BOB")
        self.assertEqual(self.datos["meta"]["industria"], "helados")
        self.assertIn("Markestrat Bolivia", self.datos["meta"]["nombre"])

    def test_cinco_segmentos_suman_cien(self):
        segmentos = self.datos["segmentos"]
        self.assertEqual(len(segmentos), 5)
        self.assertAlmostEqual(sum(s["peso"] for s in segmentos), 1.0, places=6)
        self.assertEqual([s["numero"] for s in segmentos], [1, 2, 3, 4, 5])

    def test_tres_canales_suman_cobertura(self):
        canales = self.datos["canales"]
        self.assertEqual(len(canales), 3)
        self.assertAlmostEqual(sum(c["cobertura"] for c in canales), 1.0, places=6)

    def test_seis_atributos_numerados(self):
        atributos = self.datos["atributos"]["lista"]
        self.assertEqual(len(atributos), 6)
        self.assertEqual([a["numero"] for a in atributos], [1, 2, 3, 4, 5, 6])
        for atributo in atributos:
            self.assertLess(atributo["minimo"], atributo["maximo"])

    def test_quince_estudios_con_costo(self):
        estudios = self.datos["estudios"]
        self.assertEqual(len(estudios), 15)
        self.assertEqual([e["numero"] for e in estudios], list(range(1, 16)))
        for estudio in estudios:
            self.assertGreater(estudio["costo_base"], 0)

    def test_mercado_dentro_del_rango_de_diseno(self):
        mercado = esc.mercado_potencial(self.datos)
        self.assertGreaterEqual(mercado, 40_000_000)
        self.assertLessEqual(mercado, 60_000_000)

    def test_todo_dato_declara_naturaleza_y_estado(self):
        def recorrer(nodo):
            if isinstance(nodo, dict):
                if "valor" in nodo:
                    self.assertIn(nodo.get("naturaleza"), esc.NATURALEZAS)
                    self.assertIn(
                        nodo.get("estado_verificacion"), esc.ESTADOS_VERIFICACION
                    )
                for valor in nodo.values():
                    recorrer(valor)
            elif isinstance(nodo, list):
                for valor in nodo:
                    recorrer(valor)

        recorrer(self.datos)

    def test_costo_estandar_del_producto_inicial(self):
        iniciales = self.datos["atributos_iniciales"]
        costo = esc.costo_estandar(iniciales, self.datos)
        self.assertAlmostEqual(costo, 3.36, places=2)
        self.assertAlmostEqual(costo, float(iniciales[6]), places=2)

    def test_estacionalidad_promedio_uno(self):
        pesos = [
            esc.peso_estacionalidad(mes, self.datos) for mes in range(1, 13)
        ]
        self.assertAlmostEqual(sum(pesos) / len(pesos), 1.0, places=3)
        self.assertGreater(pesos[11], pesos[5])  # diciembre > junio

    def test_resumen_cuenta_pendientes(self):
        resumen = esc.resumen(self.datos, esc.cargar_catalogo())
        self.assertEqual(resumen["segmentos"], 5)
        self.assertEqual(resumen["canales"], 3)
        self.assertEqual(resumen["estudios"], 15)
        self.assertEqual(resumen["marcas"], 10)
        self.assertGreater(resumen["datos_pendientes"], 0)


class TestValidacionEscenario(unittest.TestCase):
    def setUp(self):
        self.base = copy.deepcopy(esc.cargar_escenario())

    def _falla(self, mutador, fragmento):
        datos = copy.deepcopy(self.base)
        mutador(datos)
        with self.assertRaises(esc.ErrorEscenario) as contexto:
            esc.validar_escenario(datos)
        self.assertIn(fragmento, str(contexto.exception))

    def test_pesos_de_segmento_distintos_de_uno(self):
        self._falla(
            lambda d: d["segmentos"][0].__setitem__("peso", 0.90),
            "deben sumar 1,00",
        )

    def test_cobertura_de_canales_distinta_de_uno(self):
        self._falla(
            lambda d: d["canales"][0].__setitem__("cobertura", 0.10),
            "cobertura suma",
        )

    def test_segmento_sin_naturaleza(self):
        self._falla(
            lambda d: d["segmentos"][2].pop("naturaleza"),
            "naturaleza",
        )

    def test_dato_oficial_sin_fuente(self):
        def mutar(d):
            d["macro"]["inflacion_anual"]["fuente"] = ""

        self._falla(mutar, "debe citar 'fuente'")

    def test_dato_oficial_sin_fecha(self):
        def mutar(d):
            d["macro"]["tipo_cambio_usd"].pop("fecha")

        self._falla(mutar, "debe citar 'fecha'")

    def test_atributo_inicial_fuera_de_rango(self):
        def mutar(d):
            d["atributos_iniciales"][2] = 999

        self._falla(mutar, "fuera del rango")

    def test_estudios_incompletos(self):
        self._falla(lambda d: d["estudios"].pop(), "se esperaban 15")

    def test_moneda_distinta_de_bob(self):
        self._falla(
            lambda d: d["meta"].__setitem__("moneda", "USD"),
            "debe ser BOB",
        )

    def test_escenario_correcto_no_lanza(self):
        self.assertTrue(esc.validar_escenario(copy.deepcopy(self.base)))


class TestCatalogo(unittest.TestCase):
    def setUp(self):
        self.catalogo = esc.cargar_catalogo(recargar=True)

    def test_cinco_empresas(self):
        empresas = self.catalogo["empresas"]
        self.assertEqual(len(empresas), 5)
        codigos = {e["codigo"] for e in empresas}
        self.assertEqual(
            codigos,
            {"delizia", "pil_andina", "frigo", "panda_inal", "cabrera"},
        )

    def test_diez_marcas_ficticias_dos_por_empresa(self):
        marcas = self.catalogo["marcas"]
        self.assertEqual(len(marcas), 10)
        for marca in marcas:
            self.assertEqual(marca["naturaleza"], "ficticio")
            self.assertEqual(marca["estado_verificacion"], "no_aplica")
        por_empresa = {}
        for marca in marcas:
            por_empresa[marca["empresa"]] = por_empresa.get(marca["empresa"], 0) + 1
        self.assertEqual(set(por_empresa.values()), {2})

    def test_lineas_cubiertas(self):
        lineas = self.catalogo["lineas"]
        self.assertTrue({"agua", "mixto", "crema"} <= set(lineas))
        for nombre, linea in lineas.items():
            self.assertIn("precio_inicial", linea)
            self.assertGreater(linea["precio_inicial"], 0)

    def test_marca_con_empresa_inexistente(self):
        catalogo = copy.deepcopy(self.catalogo)
        catalogo["marcas"][0]["empresa"] = "empresa_fantasma"
        with self.assertRaises(esc.ErrorEscenario) as contexto:
            esc.validar_catalogo(catalogo)
        self.assertIn("inexistente", str(contexto.exception))

    def test_nombre_de_marca_demasiado_largo(self):
        catalogo = copy.deepcopy(self.catalogo)
        catalogo["marcas"][1]["nombre"] = "X" * 31
        with self.assertRaises(esc.ErrorEscenario) as contexto:
            esc.validar_catalogo(catalogo)
        self.assertIn("30 caracteres", str(contexto.exception))


if __name__ == "__main__":
    unittest.main()
