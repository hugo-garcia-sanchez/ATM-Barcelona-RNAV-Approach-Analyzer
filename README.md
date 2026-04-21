# P3 ATM Analyzer

Aplicación de escritorio para cargar ficheros CSV, persistirlos en SQLite, consultar resúmenes y emitir snapshots por WebSocket.

## Lo que ya hay

- API REST con FastAPI corriendo en local.
- Interfaz de escritorio con ventana nativa vía pywebview.
- Persistencia con `sqlite3`.
- Ingesta y normalización de CSV con pandas.
- WebSocket para enviar el estado del dataset cargado.
- Carpeta de entrada writable para dejar los CSV antes de procesarlos.

## Arranque local

1. Instala dependencias:

	`pip install -r requirements.txt`

2. Ejecuta la aplicación:

	`python run.py`

3. La ventana nativa se abre sola y el backend queda embebido en localhost. En Linux con Wayland, el launcher fuerza `QT_QPA_PLATFORM=xcb` para evitar problemas de WebEngine.

4. Si quieres abrir el backend solo para depuración, sigue siendo accesible en:

	`http://127.0.0.1:8000/`

5. La documentación automática de FastAPI sigue disponible en:

	`http://127.0.0.1:8000/docs`

## Endpoints principales

- `GET /api/health`
- `GET /api/datasets`
- `POST /api/datasets/upload`
- `POST /api/datasets/import-existing/{filename}`
- `GET /api/datasets/{upload_id}`
- `GET /api/datasets/{upload_id}/summary`
- `GET /api/datasets/{upload_id}/records`
- `DELETE /api/datasets/{upload_id}`
- `WS /ws/datasets/{upload_id}`

## Uso con ficheros ya copiados en data/inputs

Si el CSV ya existe en `data/inputs/`, puedes procesarlo sin subirlo por formulario:

`POST /api/datasets/import-existing/P3_04h_08h.csv`

El parser soporta CSV separados por `;` y con decimales con `,`.

## Frontend integrado

La UI se sirve desde el mismo proceso FastAPI y ya no depende de React, Leaflet ni fuentes de CDN en tiempo de ejecución.

- Panel izquierdo: seleccion de dataset, filtros de vuelo y altitud, conexion WebSocket.
- Zona central: mapa local dibujado en canvas con los puntos del dataset.
- Panel derecho: importacion de CSV existentes en la carpeta writable de entrada y carga manual de CSV.

## Estado actual

La siguiente iteración natural es empaquetar la app como ejecutable con PyInstaller y, si quieres un mapa base real sin internet, añadir una capa de teselas locales o un mapa vectorial offline.
