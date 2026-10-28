"""
Pruebas de humo de la Etapa 1.

No tocan PostgreSQL ni la base real: usan una base SQLite temporal.
Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker

import infraestructura.database as db
from core.models import Base
from infraestructura.auditoria import Hallazgo, auditar_integridad
from infraestructura.database import _crear_sqlite_fallback, enmascarar_url


class TestEnmascararUrl(unittest.TestCase):
    def test_no_expone_password(self):
        url = "postgresql://pacha_user:pacha_pass_2026@localhost:5432/pacha_db"
        oculta = enmascarar_url(url)
        self.assertNotIn("pacha_pass_2026", oculta)
        self.assertNotIn("%2A", oculta)
        self.assertIn("pacha_user", oculta)
        self.assertIn("localhost", oculta)
        self.assertIn("pacha_db", oculta)

    def test_url_sin_password(self):
        url = "sqlite:///instance/pacha_fallback.db"
        self.assertEqual(enmascarar_url(url), url)

    def test_url_invalida(self):
        self.assertEqual(enmascarar_url("no-es-una-url"), "(URL no válida)")

    def test_url_vacia(self):
        self.assertEqual(enmascarar_url(None), "(sin URL)")


class TestSqliteTemporal(unittest.TestCase):
    """Crea una BD SQLite aislada y restaura el estado global al terminar."""

    def setUp(self):
        fd, self.ruta = tempfile.mkstemp(prefix="pacha_test_", suffix=".db")
        os.close(fd)
        self.url = f"sqlite:///{self.ruta}"
        self.guardado = (db.engine, db.SessionLocal, db.DB_ACTUAL, db.DB_ES_FALLBACK)

        self.engine = _crear_sqlite_fallback(self.url)
        Base.metadata.create_all(self.engine)
        db.engine = self.engine
        db.SessionLocal = scoped_session(
            sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        )
        db.DB_ACTUAL = "sqlite"
        db.DB_ES_FALLBACK = True

    def tearDown(self):
        db.close_session()
        self.engine.dispose()
        db.engine, db.SessionLocal, db.DB_ACTUAL, db.DB_ES_FALLBACK = self.guardado
        try:
            os.remove(self.ruta)
        except OSError:
            pass

    def test_foreign_keys_activas(self):
        with self.engine.connect() as conn:
            self.assertEqual(conn.execute(text("PRAGMA foreign_keys")).scalar(), 1)

    def test_foreign_key_rechaza_huerfano(self):
        with self.engine.begin() as conn:
            with self.assertRaises(Exception):
                conn.execute(text(
                    "INSERT INTO equipos (industria_id, numero) VALUES (99999, 1)"
                ))

    def test_auditoria_devuelve_estructura(self):
        resultado = auditar_integridad()

        self.assertIn("db", resultado)
        self.assertIn("hallazgos", resultado)
        self.assertIn("resumen", resultado)
        self.assertEqual(resultado["db"]["motor"], "SQLITE")
        self.assertTrue(resultado["db"]["es_fallback"])

        self.assertIsInstance(resultado["hallazgos"], list)
        self.assertTrue(resultado["hallazgos"])
        for hallazgo in resultado["hallazgos"]:
            self.assertIn(hallazgo["nivel"], {"OK", "WARN", "FAIL"})
            self.assertIsInstance(hallazgo["codigo"], str)
            self.assertIsInstance(hallazgo["mensaje"], str)

        self.assertEqual(
            set(resultado["resumen"]),
            {"OK", "WARN", "FAIL"},
            "El resumen debe incluir siempre las tres claves.",
        )
        total = sum(resultado["resumen"].values())
        self.assertEqual(total, len(resultado["hallazgos"]))

    def test_auditoria_detecta_tablas_faltantes(self):
        """Con la BD vacía, la auditoría debe reportar tablas ausentes."""
        with self.engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS usuarios"))

        resultado = auditar_integridad()
        codigos = {h["codigo"] for h in resultado["hallazgos"]}
        self.assertIn("BD_VACIA", codigos)
        self.assertGreater(resultado["resumen"]["FAIL"], 0)


class TestApp(unittest.TestCase):
    def test_health_sin_base_inicializada(self):
        """La ruta /health responde aun antes de inicializar la BD."""
        from presentacion.web import create_app

        app = create_app()
        cliente = app.test_client()
        respuesta = cliente.get("/health")
        self.assertEqual(respuesta.status_code, 200)

        datos = respuesta.get_json()
        self.assertEqual(set(datos), {"ok", "motor", "fallback"})
        self.assertIsInstance(datos["ok"], bool)
        self.assertIsInstance(datos["fallback"], bool)

    def test_health_no_expone_credenciales(self):
        from presentacion.web import create_app

        app = create_app()
        respuesta = app.test_client().get("/health")
        cuerpo = respuesta.get_data(as_text=True)
        self.assertNotIn("pacha_pass_2026", cuerpo)
        self.assertNotIn("password", cuerpo.lower())


if __name__ == "__main__":
    unittest.main()
