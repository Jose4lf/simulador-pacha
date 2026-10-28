"""
Pruebas de la Etapa 2: autenticación, contraseñas temporales, CSRF,
aislamiento por rol y por docente.

No tocan PostgreSQL ni la base real: usan una base SQLite temporal.
Ejecutar con:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v
"""
import os
import tempfile
import unittest

from sqlalchemy import text
from sqlalchemy.orm import scoped_session, sessionmaker

import infraestructura.database as db
from aplicacion.decano_service import DecanoService
from aplicacion.profesor_service import ProfesorService
from core.models import Base, Equipo, Industria, Usuario
from infraestructura.database import _crear_sqlite_fallback
from infraestructura.seguridad import (
    generar_password_temporal, hashear_password, limpiar_todos_los_intentos,
    validar_password, verificar_password,
)
from presentacion.web import create_app

PASSWORD_BASE = "ClaveSegura1"


class TestPoliticaPassword(unittest.TestCase):
    def test_generar_temporal_cumple_politica(self):
        generadas = set()
        for _ in range(30):
            clave = generar_password_temporal()
            self.assertEqual(len(clave), 12)
            ok, mensaje = validar_password(clave, username="alguien")
            self.assertTrue(ok, mensaje)
            generadas.add(clave)
        self.assertGreater(len(generadas), 25, "Las claves deben ser aleatorias.")

    def test_rechaza_debiles(self):
        casos = [
            ("", "vacía"),
            ("abc", "corta"),
            ("abcdefgh", "sin número"),
            ("12345678", "sin letra"),
            (" clave123 ", "espacios"),
            ("usuario1", "igual al usuario"),
        ]
        for clave, motivo in casos:
            ok, _ = validar_password(clave, username="usuario1")
            self.assertFalse(ok, f"Debió rechazar: {motivo}")

    def test_acepta_valida(self):
        ok, mensaje = validar_password("BuenaClave2026", username="usuario")
        self.assertTrue(ok, mensaje)

    def test_hash_no_guarda_texto_plano(self):
        guardado = hashear_password(PASSWORD_BASE)
        self.assertNotIn(PASSWORD_BASE, guardado)
        self.assertTrue(verificar_password(guardado, PASSWORD_BASE))
        self.assertFalse(verificar_password(guardado, "OtraClave1"))

    def test_compatibilidad_texto_plano(self):
        self.assertTrue(verificar_password("legado123", "legado123"))
        self.assertFalse(verificar_password("legado123", "otra"))


class BaseConBD(unittest.TestCase):
    """Base SQLite temporal + app Flask para pruebas de integración."""

    def setUp(self):
        limpiar_todos_los_intentos()
        fd, self.ruta = tempfile.mkstemp(prefix="pacha_test2_", suffix=".db")
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

        self._crear_datos()
        self.app = create_app()
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        limpiar_todos_los_intentos()
        db.close_session()
        self.engine.dispose()
        db.engine, db.SessionLocal, db.DB_ACTUAL, db.DB_ES_FALLBACK = self.guardado
        try:
            os.remove(self.ruta)
        except OSError:
            pass

    def _crear_datos(self):
        sesion = db.SessionLocal()
        try:
            decano = Usuario(
                username="decano_test", password_hash=hashear_password(PASSWORD_BASE),
                rol="decano", nombre="Decano Test", activo=True,
                debe_cambiar_password=False,
            )
            prof_a = Usuario(
                username="profe_a", password_hash=hashear_password(PASSWORD_BASE),
                rol="profesor", nombre="Profe A", activo=True,
                debe_cambiar_password=False,
            )
            prof_b = Usuario(
                username="profe_b", password_hash=hashear_password(PASSWORD_BASE),
                rol="profesor", nombre="Profe B", activo=True,
                debe_cambiar_password=False,
            )
            sesion.add_all([decano, prof_a, prof_b])
            sesion.flush()

            ind_a = Industria(nombre="Industria A", profesor_id=prof_a.id, anio_maximo=10)
            ind_b = Industria(nombre="Industria B", profesor_id=prof_b.id, anio_maximo=10)
            sesion.add_all([ind_a, ind_b])
            sesion.flush()

            eq_a = Equipo(industria_id=ind_a.id, numero=1, nombre_empresa="Empresa A")
            eq_b = Equipo(industria_id=ind_b.id, numero=1, nombre_empresa="Empresa B")
            sesion.add_all([eq_a, eq_b])
            sesion.flush()

            alumno_a = Usuario(
                username="alumno_a", password_hash=hashear_password(PASSWORD_BASE),
                rol="alumno", nombre="Alumno A", activo=True,
                equipo_id=eq_a.id, debe_cambiar_password=False,
            )
            alumno_b = Usuario(
                username="alumno_b", password_hash=hashear_password(PASSWORD_BASE),
                rol="alumno", nombre="Alumno B", activo=True,
                equipo_id=eq_b.id, debe_cambiar_password=False,
            )
            alumno_temp = Usuario(
                username="alumno_temp", password_hash=hashear_password("Temporal1"),
                rol="alumno", nombre="Alumno Temporal", activo=True,
                equipo_id=eq_a.id, debe_cambiar_password=True,
            )
            inactivo = Usuario(
                username="inactivo", password_hash=hashear_password(PASSWORD_BASE),
                rol="alumno", nombre="Inactivo", activo=False,
                debe_cambiar_password=False,
            )
            sesion.add_all([alumno_a, alumno_b, alumno_temp, inactivo])
            sesion.commit()

            self.ids = {
                "decano": decano.id, "prof_a": prof_a.id, "prof_b": prof_b.id,
                "ind_a": ind_a.id, "ind_b": ind_b.id,
                "eq_a": eq_a.id, "eq_b": eq_b.id,
                "alumno_a": alumno_a.id, "alumno_b": alumno_b.id,
                "alumno_temp": alumno_temp.id,
            }
        finally:
            sesion.close()

    # ------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------
    def csrf(self, cliente=None):
        cliente = cliente or self.client
        cliente.get("/")
        with cliente.session_transaction() as sess:
            return sess.get("csrf_token")

    def login(self, usuario, password=PASSWORD_BASE, rol="alumno", cliente=None):
        cliente = cliente or self.client
        token = self.csrf(cliente)
        return cliente.post(
            "/login",
            data={
                "usuario": usuario, "password": password, "rol": rol,
                "csrf_token": token,
            },
        )

    def usuario(self, username):
        sesion = db.SessionLocal()
        try:
            return sesion.query(Usuario).filter_by(username=username).first()
        finally:
            sesion.close()

    def con_sesion(self, rol):
        with self.client.session_transaction() as sess:
            sess["usuario_id"] = self.ids[rol]
            sess["usuario"] = rol
            sess["rol"] = {"prof_a": "profesor", "alumno_a": "alumno", "decano": "decano"}[rol]
            sess["nombre"] = rol
            sess["debe_cambiar_password"] = False


class TestLoginYCSRF(BaseConBD):
    def test_post_sin_csrf_se_rechaza(self):
        respuesta = self.client.post(
            "/login",
            data={"usuario": "alumno_a", "password": PASSWORD_BASE, "rol": "alumno"},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_login_correcto_redirige_al_panel(self):
        respuesta = self.login("alumno_a", rol="alumno")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/alumno/panel", respuesta.headers["Location"])

    def test_login_rol_incorrecto_no_abre_sesion(self):
        respuesta = self.login("alumno_a", rol="profesor")
        self.assertEqual(respuesta.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertNotIn("usuario_id", sess)

    def test_login_usuario_inactivo_rechazado(self):
        respuesta = self.login("inactivo", rol="alumno")
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("Credenciales incorrectas", respuesta.get_data(as_text=True))

    def test_limite_de_intentos(self):
        for _ in range(5):
            self.login("alumno_a", password="Incorrecta1", rol="alumno")
        respuesta = self.login("alumno_a", password="Incorrecta1", rol="alumno")
        self.assertEqual(respuesta.status_code, 429)

    def test_rol_de_sesion_se_revalida_en_bd(self):
        self.login("alumno_a", rol="alumno")
        with self.client.session_transaction() as sess:
            sess["rol"] = "decano"  # intento de escalada en la cookie firmada
        respuesta = self.client.get("/decano/panel")
        self.assertNotEqual(respuesta.status_code, 200)


class TestCambioObligatorio(BaseConBD):
    def test_login_temporal_redirige_a_cambio(self):
        respuesta = self.login("alumno_temp", password="Temporal1", rol="alumno")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cambiar-password", respuesta.headers["Location"])

    def test_panel_bloqueado_hasta_cambiar(self):
        self.login("alumno_temp", password="Temporal1", rol="alumno")
        respuesta = self.client.get("/alumno/panel")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/cambiar-password", respuesta.headers["Location"])

    def test_cambio_exitoso_actualiza_hash_y_flag(self):
        self.login("alumno_temp", password="Temporal1", rol="alumno")
        token = self.csrf()
        respuesta = self.client.post(
            "/cambiar-password",
            data={
                "actual": "Temporal1",
                "nueva": "NuevaClave99",
                "confirmar": "NuevaClave99",
                "csrf_token": token,
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/", respuesta.headers["Location"])

        alumno = self.usuario("alumno_temp")
        self.assertFalse(alumno.debe_cambiar_password)
        self.assertIsNotNone(alumno.password_actualizada)
        self.assertTrue(verificar_password(alumno.password_hash, "NuevaClave99"))
        self.assertFalse(verificar_password(alumno.password_hash, "Temporal1"))

    def test_cambio_rechaza_actual_incorrecta(self):
        self.login("alumno_temp", password="Temporal1", rol="alumno")
        token = self.csrf()
        respuesta = self.client.post(
            "/cambiar-password",
            data={
                "actual": "NoEsLaActual1",
                "nueva": "NuevaClave99",
                "confirmar": "NuevaClave99",
                "csrf_token": token,
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("no es correcta", respuesta.get_data(as_text=True))

    def test_cambio_rechaza_politica_debil(self):
        self.login("alumno_temp", password="Temporal1", rol="alumno")
        token = self.csrf()
        respuesta = self.client.post(
            "/cambiar-password",
            data={
                "actual": "Temporal1",
                "nueva": "corta",
                "confirmar": "corta",
                "csrf_token": token,
            },
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("al menos", respuesta.get_data(as_text=True))


class TestAislamiento(BaseConBD):
    def test_profesor_no_ve_industria_ajena(self):
        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(f"/profesor/simulaciones/{self.ids['ind_b']}")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/profesor/simulaciones", respuesta.headers["Location"])

    def test_profesor_no_elimina_industria_ajena(self):
        self.login("profe_a", rol="profesor")
        token = self.csrf()
        respuesta = self.client.post(
            f"/profesor/simulaciones/{self.ids['ind_b']}/eliminar",
            data={"csrf_token": token},
        )
        self.assertEqual(respuesta.status_code, 404)

        sesion = db.SessionLocal()
        try:
            self.assertIsNotNone(sesion.query(Industria).filter_by(id=self.ids["ind_b"]).first())
        finally:
            sesion.close()

    def test_profesor_no_edita_alumno_ajeno(self):
        self.login("profe_a", rol="profesor")
        respuesta = self.client.get(f"/profesor/alumnos/{self.ids['alumno_b']}/editar")
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn("/profesor/contrasenas", respuesta.headers["Location"])

    def test_profesor_no_resetea_alumno_ajeno(self):
        self.login("profe_a", rol="profesor")
        token = self.csrf()
        respuesta = self.client.post(
            f"/profesor/alumnos/{self.ids['alumno_b']}/resetear",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(respuesta.status_code, 404)
        self.assertTrue(verificar_password(self.usuario("alumno_b").password_hash, PASSWORD_BASE))

    def test_profesor_resetea_su_alumno_con_clave_aleatoria(self):
        self.login("profe_a", rol="profesor")
        token = self.csrf()
        respuesta = self.client.post(
            f"/profesor/alumnos/{self.ids['alumno_a']}/resetear",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(respuesta.status_code, 200)
        datos = respuesta.get_json()
        self.assertTrue(datos["ok"])
        self.assertNotIn(datos["nueva_pass"], {"PASSWORD", "alumno123", "pacha2026"})

        alumno = self.usuario("alumno_a")
        self.assertTrue(alumno.debe_cambiar_password)
        self.assertTrue(verificar_password(alumno.password_hash, datos["nueva_pass"]))


class TestServiciosPassword(BaseConBD):
    def test_crear_profesor_genera_clave_temporal(self):
        resultado = DecanoService.crear_profesor(
            "profe_nuevo", None, "Profe Nuevo", "nuevo@example.com"
        )
        self.assertTrue(resultado["ok"])
        clave = resultado["password_temporal"]
        ok, mensaje = validar_password(clave, "profe_nuevo")
        self.assertTrue(ok, mensaje)

        usuario = self.usuario("profe_nuevo")
        self.assertTrue(usuario.debe_cambiar_password)
        self.assertNotIn(clave, usuario.password_hash)

    def test_reset_decano_no_usa_claves_fijas(self):
        resultado = DecanoService.resetear_password_usuario(self.ids["alumno_a"])
        self.assertTrue(resultado["ok"])
        self.assertNotIn(resultado["nueva_pass"], {"PASSWORD", "123", "pacha2026"})
        self.assertTrue(self.usuario("alumno_a").debe_cambiar_password)

    def test_no_se_puede_desactivar_decano(self):
        resultado = DecanoService.eliminar_usuario(self.ids["decano"])
        self.assertIn("error", resultado)
        self.assertTrue(self.usuario("decano_test").activo)

    def test_importar_csv_genera_claves_y_aisla_errores(self):
        contenido = (
            "equipo_numero,numero_alumno,nombre,email\n"
            "1,1,Ana Perez,ana@example.com\n"
            "99,1,Fila Mala,mala@example.com\n"
        )
        resultado = ProfesorService.importar_alumnos_csv(self.ids["ind_a"], contenido)

        self.assertEqual(len(resultado["creados"]), 1)
        self.assertEqual(len(resultado["errores"]), 1)
        creado = resultado["creados"][0]
        self.assertNotIn(creado["password"], {"alumno123", "PASSWORD"})
        self.assertTrue(verificar_password(
            self.usuario(creado["username"]).password_hash, creado["password"]
        ))
        self.assertTrue(self.usuario(creado["username"]).debe_cambiar_password)


class TestDecanoNoSeAutoBloquea(BaseConBD):
    def test_decano_no_resetea_su_propia_clave_por_ajax(self):
        self.login("decano_test", rol="decano")
        token = self.csrf()
        respuesta = self.client.post(
            f"/decano/usuarios/{self.ids['decano']}/resetear",
            headers={"X-CSRFToken": token},
        )
        self.assertEqual(respuesta.status_code, 400)

    def test_decano_no_desactiva_su_cuenta(self):
        self.login("decano_test", rol="decano")
        token = self.csrf()
        respuesta = self.client.post(
            f"/decano/usuarios/{self.ids['decano']}/eliminar",
            data={"csrf_token": token},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(self.usuario("decano_test").activo)


if __name__ == "__main__":
    unittest.main()
