# PACHA Simulador

App Flask + SQLAlchemy que simula el juego de marketing LABSAG Markestrated (5 segmentos, 3 canales, 15 estudios, años 0–10). UI, rutas y nombres de dominio están en español: mantenlos así.

## Comunicación y alcance

- Responde, analiza y documenta en español; conserva en inglés comandos, rutas, nombres de archivo y términos técnicos.
- No elimines funcionalidades ni agregues dependencias sin autorización. Pide confirmación antes de DROP, resets o borrados masivos.
- Para funcionalidades grandes, propone un plan por etapas. No afirmes haber ejecutado pruebas que no corriste.

## Entorno y comandos

- Usa el venv del repo: `.venv/Scripts/python.exe` (Git Bash) o activa `.venv\Scripts\activate`. El `python` global **no** tiene Flask/SQLAlchemy instalados.
- La consola de Windows usa `cp1252` y los scripts imprimen emojis (`✅`, `⚠️`): fallan con `UnicodeEncodeError`. Ejecuta con `PYTHONIOENCODING=utf-8` (`set PYTHONIOENCODING=utf-8` en cmd).
- `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe inicializar_sistema.py` — bootstrap idempotente: tablas, usuario `Admin` / `321`, simulador `markestrated` y 15 estudios con costo placeholder `10000`.
- `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/cargar_estudios_mercado.py` — upsert de esos 15 estudios con nombres y costos reales. Ejecútalo después del inicializador.
- `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe run.py` — servidor de desarrollo en `0.0.0.0:${PORT:-5000}`. En Windows usa esto; `gunicorn run:app` (`Procfile`) es solo para producción Unix.
- La suite usa `unittest` (pytest no está instalado) y SQLite temporal: `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -m unittest discover -s tests -v`. Al cierre de la Etapa 5 son 102 pruebas. Verifica además el arranque con `PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe -c "from presentacion.web import create_app; create_app()"`.
- `run.py` ejecuta `inicializar_db()` al importarse: importar `run` conecta a la BD y crea tablas. Para smoke tests importa `presentacion.web`.
- `scripts/inspeccionar_bd.py` y `ver_tablas.py` inspeccionan tablas. `scripts/inspeccionar_bd.py` y `scripts/resetear_sistema.py` hacen DROP de todo tras escribir `SI`; nunca los ejecutes de forma no interactiva.
- `scripts/reparar_reportes_anio0.py` rellena reportes de Año 0 faltantes. `scripts/regenerar_reportes_anio0.py` recalcula todos los reportes de Año 0 (dry-run por defecto; `--aplicar` escribe un respaldo JSON antes de reemplazar). `scripts/auditar_integridad.py` es la auditoría de solo lectura.
- Migraciones: `.venv/Scripts/alembic.exe upgrade head`, `current` y `check`. `check` debe decir «No new upgrade operations detected».

## Arquitectura

- `run.py` inicializa la BD y `presentacion/web/__init__.py:create_app()` registra cuatro blueprints: `auth` (sin prefijo), `/alumno`, `/profesor`, `/decano`.
- Capas: rutas en `presentacion/web/blueprints/*/routes.py` → servicios en `aplicacion/*_service.py` → modelos/motor en `core/` → sesiones en `infraestructura/database.py`.
- Los servicios abren una sesión por método y la cierran en `finally`. Devuelven dicts/listas: convierte los objetos ORM dentro del `try`; acceder a relaciones lazy después del cierre provoca `DetachedInstanceError`.
- `aplicacion/profesor_service.py` contiene un segundo `SimulacionService` y `_generar_datos_estudios` sin uso. La implementación viva es `aplicacion/simulacion_service.py`; no edites la copia muerta.
- Valores efectivos del dominio: constantes `PERFILES_MARKETING` y `ATRIBUTOS_FISICOS_INICIALES` en `ProfesorService`, el `mercado_total=1300000` hardcodeado en los servicios de simulación, las constantes de `core/motor_simulacion.py` y las reglas de I&D de `core/modelo_id.py`. `datos/parametros.yaml` y `core/escenarios.py` no se leen.
- El Año 0 no es una ronda del motor: `core/reportes_anio0.py:generar_reporte_anio0` construye el diagnóstico inicial con las mismas unidades del motor (mercado en unidades; producción/ventas/inventario en miles; importes en miles de Bs). Las participaciones históricas se normalizan globalmente a 100 %.
- Estudios de mercado: al enviar la decisión se registra `CompraEstudio` con el costo congelado; al procesar la ronda, `SimulacionService._generar_datos_estudios` genera los resultados y el costo se carga a `Reporte.investigacion_mercado`.
- I&D: `aplicacion/proyecto_service.py` registra proyectos en `proyectos`/`proyecto_atributos`, los evalúa en la ronda y guarda `proyecto_resultados`. En la hoja de decisiones del año siguiente el equipo aplica un proyecto aprobado a una marca existente o lanza una marca nueva; `Marca.costo_unitario` alimenta el motor y `Marca.calidad_actual` usa el índice propio de PACHA. Los proyectos se evalúan con sorteo determinista por industria/equipo/nombre/año.
- `infraestructura/repositorio.py` solo se usa para `UsuarioRepo.obtener_por_username`. El resto está duplicado o mal ubicado dentro de `EstudioMercadoRepo`; agrega consultas a los servicios, no a ese archivo.

## Base de datos

- `.env` (gitignored) define `DATABASE_URL`, `FALLBACK_SQLITE`, `SECRET_KEY`, `DEBUG`. `config.py` lo carga al importar.
- Al arrancar intenta PostgreSQL y, si falla, cae **silenciosamente** a SQLite en `instance/pacha_fallback.db`. Si “faltan datos”, revisa la línea de consola con el motor activo; usa `FALLBACK_SQLITE=false` para fallar de forma visible.
- Hay migraciones Alembic en `migrations/versions/` (rama base `3c9e1b7a5d20`, Etapa 5 en `9f2a1c7d4e10`). `inicializar_db()` sigue haciendo `Base.metadata.create_all()`: crea tablas faltantes pero no altera columnas; todo cambio de esquema debe ir con una migración. No apliques `upgrade` sin respaldo `pg_dump` previo.
- Usa `infraestructura.database.get_session()`. Flask-SQLAlchemy está instalado pero no se usa; no recurras a `db.session`.
- Credenciales por defecto: `Admin` / `321` (inicializador); `scripts/resetear_decano.py` crea o resetea `admin` / `123`. Las cuentas rotadas al cierre de la Etapa 2 tienen clave temporal y `debe_cambiar_password=true`.

## Convenciones y trampas

- Auth manual: cada ruta repite el chequeo de `session["rol"]` y el login exige que el rol enviado coincida con `Usuario.rol` (`decano`, `profesor`, `alumno`). Hay CSRF global (`before_request` en `presentacion/web/__init__.py`): todo POST nuevo necesita `csrf_token`. Agrega el chequeo de rol en toda ruta nueva.
- El cambio obligatorio de contraseña se aplica en el `before_request`; los smoke tests con sesión inyectada redirigen a `/cambiar-password` si la cuenta lo tiene pendiente.
- Templates en `presentacion/web/templates/<rol>/` con `render_template("<rol>/page.html", ...)`; los `template_folder` de los blueprints son inconsistentes, así que usa la carpeta a nivel de app.
- `requirements.txt` está en UTF-8 con LF (se convirtió desde UTF-16 LE para que pip lo lea en Linux). `alembic` va declarado explícitamente porque el *pre-deploy* lo invoca.
- `.gitattributes` exige LF y el working tree suele estar en CRLF: ignora los warnings y no reformatees archivos masivamente.
- Despliegue en Render: el build usa `requirements.txt`, el arranque es `gunicorn run:app` y el esquema se actualiza con `alembic upgrade head` como *Pre-Deploy Command*. `run.py` solo hace `create_all()`, que no altera columnas: sin migración, un esquema viejo rompe el login con `UndefinedColumn`. `ProxyFix` está activo para recuperar IP y esquema detrás del proxy. `FLASK_ENV=production` exige `SECRET_KEY` definida o `create_app()` no arranca.
