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

# Contexto del Proyecto: ATM Barcelona RNAV Approach Analyzer

## 1. Estado Actual del Proyecto

El proyecto se encuentra en una fase funcional de prototipo avanzado para una aplicación de escritorio dedicada al análisis de trayectorias de vuelo (despegues y aproximaciones) en el entorno del Aeropuerto de Barcelona (LEBL).

### Capacidades Implementadas:
- **Backend Robusto**: Desarrollado con **FastAPI**, proporcionando una API REST completa y soporte para WebSockets.
- **Interfaz de Escritorio**: Utiliza **pywebview** para encapsular el frontend web en una ventana nativa, facilitando su uso como aplicación local.
- **Gestión de Datos**: Implementa persistencia mediante **SQLite** y procesamiento de datos con **Pandas**.
- **Ingesta de Datos**: Soporta la carga de ficheros CSV, con lógica específica para normalizar formatos (delimitadores, decimales) y validar campos aeronáuticos.
- **Visualización Geoespacial**: Integra un mapa interactivo basado en **Leaflet.js** para mostrar trayectorias.
- **Procesamiento ASTERIX**: Incluye módulos preparados para la decodificación de datos radar (CAT048, CAT021), aunque el flujo principal actual se centra en CSVs ya procesados.

---

## 2. Estructura y Jerarquía de Archivos

```text
ATM-Barcelona-RNAV-Approach-Analyzer/
├── run.py                       # Punto de entrada principal (arranca backend + UI nativa)
├── P3_ATM_Analyzer/             # Paquete principal del Backend
│   ├── app.py                   # Configuración y creación de la app FastAPI
│   ├── api/                     # Definición de Endpoints
│   │   └── routes/              # Rutas: datasets, health, websocket
│   ├── data_processing/         # Lógica de carga y procesamiento
│   │   ├── csv_loader.py        # Parser de ficheros CSV
│   │   ├── asterix_processor.py # Decodificación ASTERIX (preparado)
│   │   └── flight_plan_loader.py# Carga de planes de vuelo
│   ├── geospatial/              # Utilidades geográficas
│   │   └── coordinate_transform.py # Proyecciones y transformaciones
│   ├── services/                # Capa de servicio (lógica de negocio)
│   │   ├── ingest.py            # Orquestación de la carga de datos
│   │   └── realtime.py          # Gestión de actualizaciones en tiempo real
│   ├── database.py              # Configuración de SQLite (SQLAlchemy/Raw)
│   ├── schemas.py               # Modelos de datos (Pydantic)
│   └── data_store.py            # Almacenamiento temporal en memoria
├── frontend/                    # Archivos de la interfaz de usuario
│   ├── index.html               # Estructura principal
│   ├── main.js                  # Lógica de la UI y control del mapa
│   ├── api-client.js            # Cliente para comunicación con el backend
│   └── styles.css               # Estilos visuales
├── data/                        # Almacenamiento de archivos y DB
│   ├── app.db                   # Base de datos SQLite
│   └── inputs/                  # Carpeta para colocar CSVs de entrada
├── project_plan/                # Documentación de diseño y objetivos
│   ├── BLUEPRINT_...            # Documento maestro de arquitectura
│   └── cosas que faltan.md      # Roadmap de tareas pendientes
├── requirements.txt             # Dependencias del proyecto
└── test_fixes.py                # Scripts de utilidad/testeo
```

---

## 3. Funcionamiento del Sistema

### Flujo de Trabajo:
1.  **Arranque**: `run.py` inicia un servidor `uvicorn` en segundo plano y abre una ventana de `pywebview` apuntando al servidor local.
2.  **Carga de Datos**: El usuario puede subir un archivo CSV desde la UI o importar uno ya existente en `data/inputs/`.
3.  **Procesamiento**:
    - El backend valida el CSV y lo transforma en un DataFrame de Pandas.
    - Los registros se insertan en la base de datos SQLite para persistencia.
    - Se calculan parámetros básicos (velocidad, altitud corregida).
4.  **Visualización**:
    - La UI solicita los registros a la API (`/api/datasets/{id}/records`).
    - Los datos se muestran en una tabla paginada.
    - Las coordenadas se proyectan en el mapa de Leaflet, dibujando las trayectorias de las aeronaves.
5.  **Análisis**: El sistema permite filtrar por altitud, callsign y otros parámetros para aislar despegues específicos o comportamientos (como el cumplimiento de NADP).

### Componentes Clave:
- **FastAPI + Uvicorn**: Gestionan las peticiones de forma asíncrona.
- **SQLAlchemy/SQLite**: Garantiza que los datos no se pierdan al cerrar la aplicación.
- **Leaflet**: Renderiza el mapa sin necesidad de dependencias pesadas, permitiendo ver los puntos radar sobre la geografía de Barcelona.
- **WebSockets**: Permiten notificar a la interfaz sobre el progreso de cargas pesadas o cambios en el estado del servidor.

