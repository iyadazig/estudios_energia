# Prompt para dar contexto a una nueva IA

Copia y pega el texto siguiente en la nueva IA (Cursor, Claude Code, ChatGPT, Copilot, etc.)
al empezar. Si la herramienta tiene acceso al repositorio, pídele primero que lea
`CONTEXT.md`, `README.md`, `estudios/models.py` y `estudios/calculo.py`.

---

Vas a continuar el desarrollo de una aplicación web ya existente. Trabaja siempre **en español**
(código, comentarios, interfaz y mensajes de commit) y **no rompas los 31 tests** que ya pasan.

## Qué es el proyecto
Aplicación web interna de **GE&PE Ingeniería** para **estudios de renovación de contratos
eléctricos**: compara el coste anual sin IVA del contrato actual de un cliente frente a las ofertas
de varias comercializadoras, a partir del consumo histórico y de los parámetros regulados vigentes
(peajes, cargos, pérdidas, IEE, servicios de ajuste SSAA). Exporta el comparativo a Excel y PDF.
Es un proyecto de Trabajo Fin de Máster, en uso interno real en la empresa. Modalidad soportada:
**precio fijo** (el indexado es fase futura).

## Stack
Python 3.12 · Django 6.0 · SQLite · openpyxl (Excel) · xhtml2pdf + Pillow (PDF) · python-decouple
(.env) · WhiteNoise + Gunicorn (producción). Front-end sin frameworks: HTML + CSS propio con
sistema de diseño de variables en `static/css/app.css`, y JavaScript vanilla. No hay Node.

## Documentación que DEBES leer antes de tocar nada
- **`CONTEXT.md`** (raíz): arquitectura, lógica del motor de cálculo, decisiones de diseño y su
  porqué, trampas conocidas, cómo verificar y roadmap. Es la guía principal para continuar.
- **`README.md`**: instalación, ejecución, funcionalidades, usuario de prueba, despliegue.
- **`estudios/models.py`** y **`estudios/calculo.py`**: el modelo de datos y el motor de cálculo
  (el núcleo del dominio; la parte más delicada, verificada al céntimo por tests).

## Estructura mínima
- App Django `estudios` dentro del proyecto `config`. Módulos clave: `models.py`, `calculo.py`
  (motor), `exportar.py` (Excel/PDF), `importador.py` (plantilla Excel), `views.py`, `forms.py`,
  `parametros_excel.py`, `consumo.py`, `graficos.py`.
- Plantillas en `templates/` (base + una por pantalla). CSS en `static/css/app.css`. El PDF usa
  `templates/estudios/informe_pdf.html` con estilo propio (no comparte el CSS de la web).
- Comandos de gestión: `cargar_parametros_2026`, `copia_seguridad`, `seed_demo`.

## Cómo arrancar y probar
1. `python -m venv .venv` y activar; `pip install -r requirements.txt`.
2. Copiar `.env.example` → `.env` y poner una `SECRET_KEY` (`DEBUG=True` en local).
3. `python manage.py migrate` y `python manage.py seed_demo` (crea usuarios de prueba `demo` /
   `Demo.2026` y `tecnico` / `Demo.2026`, carga parámetros y un expediente de ejemplo).
4. `python manage.py runserver` → http://127.0.0.1:8000
5. **Tras cualquier cambio, ejecuta `python manage.py test estudios` y confirma que los 31 tests
   siguen en verde.** El motor de cálculo se comprueba al céntimo contra una aritmética de
   referencia independiente escrita en los propios tests: si cambias `calculo.py`, no rompas eso.

## Reglas y convenciones
- **Español** en todo. Números en formato es-ES (coma decimal); ojo con `USE_THOUSAND_SEPARATOR`.
- Pérdidas, IEE e impuesto local se guardan en **tanto por uno** (0,015 = 1,5 %).
- Acceso "todos ven todo" (uso interno); roles admin/técnico vía `is_staff`. El filtro "Mis
  expedientes" es una vista por defecto, no control de permisos.
- No versionar `.env`, `db.sqlite3`, `.venv`, `backups/`, `media/`, `staticfiles/`.
- No expongas datos de clientes reales en material público.

## En qué se puede seguir trabajando (roadmap)
- Prueba con factura real (objetivo: desviación < 1 %).
- KPI de "ahorro adjudicado" en la portada (materializar el ahorro al adjudicar, sin recalcular
  comparativos en el listado).
- Precio indexado (OMIE/ESIOS) — fase 3.
- Integración con APIs de datos (Datadis y la API de facturación de la empresa) con capa de
  adaptadores — fase 2.
- Profile factors de 2.0TD y de Canarias/Baleares.
- Decisión pendiente: ¿aplicar el impuesto local 1,5 % al precio fijo o solo al indexado?

## Cómo quiero que trabajes
Antes de implementar algo grande, propón un plan breve. Haz cambios pequeños y verificables,
ejecuta los tests, y explícame en español qué has hecho. Si tocas el cálculo, añade o ajusta el
test correspondiente. Pregúntame cuando una decisión sea de negocio (no la asumas).
