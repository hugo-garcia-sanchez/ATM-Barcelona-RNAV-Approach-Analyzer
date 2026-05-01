# ATM-Barcelona-RNAV-Approach-Analyzer — Blueprint
## Backend & Frontend Architecture Document

**Fecha**: 1 mayo 2026  
**Proyecto Base**: ASTERIX Decoder Project  
**Nuevo Proyecto**: ATM-Barcelona-RNAV-Approach-Analyzer  
**Scope**: Análisis estadístico de parámetros operativos en despegues (RWY 24L, RWY 06R)

---

## 1. VISIÓN GENERAL DEL PROYECTO

### 1.1 Objetivo
Calcular y presentar estadísticas de **parámetros técnico-operativos** en despegues exclusivamente por las dos pistas más utilizadas:
- **RWY 24L** (24 Left)
- **RWY 06R** (06 Right)

**Fundamento Aeronáutico**: El análisis se centra en despegues (no aproximaciones) porque:
- Los despegues tienen perfiles de vuelo más variables y predecibles
- Las separaciones están regidas por reglas estrictas (radar mínimo 2.5NM/90s, estela, LoA)
- Los procedimientos de ruido (NADP) son críticos en Barcelona para gestionar impacto ambiental
- Las pistas 24L y 06R representan el 85%+ de movimientos totales

### 1.2 Datos de Entrada
- **Formato**: CSV (NO archivos .AST)
- **Contenido esperado**: Datos radar ASTERIX compilados + Planes de vuelo de despegue
- **Período**: 4 horas de operaciones
- **Estructura de datos**: Posiciones radar a intervalos variables (típicamente 4-8 segundos en SSR primario, 1-2 segundos en Mode-S)
- **Origen de datos**: Extractos de Sistema de Vigilancia de Área Terminal (ATS) Barcelona

### 1.3 Salidas Principales
1. **Tabla interactiva** con datos procesados y filtrados
   - Registros de cada despegue con parámetros aerodinámicos
   - Separaciones calculadas (radar, estela, LoA)
   - Estado de cumplimiento normativo
   
2. **Mapa visual** con rutas de despegue y puntos críticos
   - Trayectorias proyectadas en sistema de referencia estereográfico
   - Identificación de puntos de viraje y zonas críticas
   - Capas de visualización: runways, SIDs, puntos de referencia
   
3. **Exportación KML** para SIG (Google Earth, QGIS, etc.)
   - Trayectorias editables, información de vuelo asociada
   - Compatible con análisis geoespacial posterior
   
4. **Estadísticas y gráficos** (barras, círculos, agrupaciones)
   - Distribuciones de separaciones (histogramas, percentiles)
   - Análisis de cumplimiento de normas
   - Relación entre tipo NADP y parámetros operacionales
   
5. **CSV exportado** con resultados finales
   - Formato UTF-8, delimitador `;`, decimal `,` (estándar español)
   - Trazabilidad completa de cálculos

### 1.4 Stack Tecnológico
| Componente | Tecnología | Justificación |
|-----------|-----------|--------------|
| Backend | Python (Flask/FastAPI) | Ecosistema científico (Pandas, NumPy), procesamiento ágil |
| Base Datos | Pandas + CSV | Datasets < 500MB; simplicidad; no requiere SGBD complejo |
| Frontend | HTML5 + CSS3 + JavaScript | Compatibilidad universal, sin instalación cliente |
| Comunicación | WebSocket (real-time) | Progreso en tiempo real sin polling; bajo overhead |
| Mapas | Leaflet.js + GeoJSON | Liviano, open-source, suficiente para análisis operacional |
| Tablas | DataTables / Tabulator.js | Interactividad, filtrado cliente-side para responsividad |
| Gráficos | Chart.js / Plotly.js | Visualización estadística clara, sin dependencias pesadas |
| Geomatica | Translib / geoutils | Proyección estereográfica precisa para coordenadas Barcelona |

---

## 2. FUNDAMENTOS AERONÁUTICOS

### 2.1 Reglas de Separación en Despegue

#### Separación Radar Mínima (RMS)
- **Valor**: 2.5 NM (4.63 km) o 90 segundos, **lo que sea mayor**
- **Aplicación**: Entre dos aeronaves consecutivas en despegue desde misma pista
- **Fundamento**: Exactitud radar primario SSR (±300m en azimut, ±500m en distancia)
- **Cálculo**: 
  ```
  Sep_radar = √[(Δx)² + (Δy)²]  (en NM, desde posiciones radar)
  Sep_tiempo = t₂ - t₁  (diferencia temporal entre despegues)
  Cumplimiento: Sep_radar ≥ 2.5 NM O Sep_tiempo ≥ 90s
  ```

#### Separación de Estela (Wake Separation)
- **Aplicación**: Cuando aeronave pesada precede a más ligera
- **Categorías** (según MTOW):
  - Heavy: > 136,000 kg (p.ej. B777, A380)
  - Medium: 7,000-136,000 kg (p.ej. B737, A320)
  - Light: < 7,000 kg (p.ej. C172, C208)
- **Regla de estela typical** (ICAO):
  - Heavy → Light: 4 NM o 180s
  - Heavy → Medium: 3 NM o 120s
  - Medium → Light: 3 NM o 120s
  - Mismo tipo: RMS (2.5 NM / 90s)

#### Separación según LoA (Letter of Agreement)
- **Definición**: Acuerdos locales entre Enfoque Barcelona y Operadores/Aeropuerto
- **Aplicación**: Pueden ser más permisivos que reglas ICAO bajo ciertas condiciones
- **Variaciones posibles**:
  - Por procedimiento de despegue (SID específico)
  - Por hora del día (peak vs. off-peak)
  - Por condiciones de visibilidad/meteorología
- **Documentación**: Disponible en Carta Aeronáutica Barcelona, OPD (Operaciones)

### 2.2 Procedimientos de Ruido (NADP)

**NADP** (Noise Abatement Departure Procedure) = procedimientos para minimizar impacto sonoro en comunidades adyacentes

#### Tipos NADP en Barcelona
- **NADP 1** (Perfil reducido): Despegue a potencia reducida, aceleración lenta
- **NADP 2** (Perfil estándar): Despegue a potencia completa, SID estándar
- **NADP 3** (Perfil alto): Despegue a potencia completa + ascenso rápido
- **Variantes locales**: Según restricciones horarias y comunidades afectadas

#### Clasificación por Parámetros (IAS a Altitud Específica)
La mayoría de NADP se clasifican por **indicadores aerodinámicos**:
- IAS a 1,500 ft: Debe estar entre ciertos rangos
- IAS a 3,000 ft: Discriminador principal
- Tasa de ascenso: Complementario
- Configuración de flaps: Determ diferencia vs. perfil estándar

**Ejemplo de Clasificación**:
```
SI (IAS a 3000ft) en rango [150, 170] kts  →  NADP 1 (reducido)
SI (IAS a 3000ft) en rango [170, 200] kts  →  NADP 2 (estándar)
SI (IAS a 3000ft) > 200 kts                →  NADP 3 (alto)
```

### 2.3 Geometría de Runway y Sistemas de Referencia

#### Runway 24 Left (RWY 24L)
- **Orientación**: Hacia 240° (rumbo magnético)
- **Umbral (Threshold)**: LAT 41.2865°N, LON 2.0759°E (aproximado)
- **Fin de Runway**: LAT ~41.2920°N, LON ~2.0650°E (aproximado, 2.5NM)
- **SIDs típicas**: Hacia norte/noroeste (sobrevuelo poblado limitado a primeras millas)

#### Runway 06 Right (RWY 06R)
- **Orientación**: Hacia 60° (rumbo magnético)
- **Umbral**: LAT ~41.2870°N, LON ~2.0760°E (aproximado)
- **Fin de Runway**: LAT ~41.3000°N, LON ~2.1050°E (aproximado)
- **SIDs típicas**: Hacia este/noreste (sobrevuelo mar minimiza impacto sonoro)

#### Transformación de Coordenadas
- **WGS84** (GPS): Lat/Lon elipsoidales, referencia global
- **Sistema Local (Estereográfico)**: X/Y planos centrados en Barcelona
  - Origen: Aproximadamente LAT 41.2865°, LON 2.0759°
  - Proyección: Estereográfica o Mercator conforme
  - Propósito: Cálculos de distancia/separación locales sin distorsión

**Fórmula de Haversine** (distancia entre dos puntos WGS84):
```
Δσ = 2 · arcsin(√[sin²(Δφ/2) + cos(φ₁)·cos(φ₂)·sin²(Δλ/2)])
d = R · Δσ   (R = 6371 km, radio medio Tierra)
d_NM = d / 1.852
```

### 2.4 Procesamiento e Interpolación de Datos Radar

#### Intervalos de Datos Radar
- **SSR Primario**: Típicamente cada 4-8 segundos (resolución radar)
- **Mode-S (ADS-B)**: Típicamente cada 1-2 segundos (más preciso)
- **Mezclado**: AIS/radar integrado puede tener gaps

#### Interpolación a 1 Segundo
**Justificación**: Muchos cálculos requieren precisión temporal; la interpolación:
- Proporciona muestreo uniforme
- Permite detección de puntos críticos (viraje, umbral)
- No introduce error significativo en intervalos cortos
- Típicamente lineal en posición, forward-fill en campos discretos

**Algoritmo**:
```
1. Agrupar datos por aircraft_id
2. Para cada grupo ordenar por time
3. Crear serie temporal uniforme (1 segundo)
4. Interpolar posición (lat, lon) linealmente
5. Interpolar altitude: lineal
6. Interpolar speed (IAS, GS): lineal
7. Forward-fill campos discretos (NADP, SID, etc.)
```

---

## 3. ESTRUCTURA DE CARPETAS

```
ATM-Barcelona-RNAV-Analyzer/
├── main.py                          # Punto de entrada principal
├── requirements.txt                 # Dependencias Python
├── README.md                        # Guía de uso
├── .env                            # Variables de entorno (puerto, rutas, etc.)
│
├── backend/
│   ├── __init__.py
│   ├── app.py                      # Aplicación Flask/FastAPI
│   ├── config.py                   # Configuración centralizada
│   │
│   ├── data_processing/            # Lógica de procesamiento de datos
│   │   ├── __init__.py
│   │   ├── csv_loader.py          # Lectura y validación de CSV
│   │   ├── data_validator.py      # Validación de datos de entrada
│   │   ├── asterix_handler.py     # Procesamiento de datos ASTERIX
│   │   ├── flight_plan_handler.py # Lectura y relación de planes de vuelo
│   │   ├── runway_filter.py       # Filtros geográficos por pista (24L, 06R)
│   │   └── interpolation.py       # Interpolación a 1 segundo
│   │
│   ├── calculations/               # Cálculos estadísticos y operacionales
│   │   ├── __init__.py
│   │   ├── separation_calculator.py      # Cálculo de separaciones consecutivas
│   │   ├── radar_separation.py           # Separación mínima radar
│   │   ├── wake_separation.py            # Separación por estela (distancia/tiempo)
│   │   ├── loa_calculator.py             # Cálculo según LoA (Letter of Agreement)
│   │   ├── turn_detection.py             # Detección de punto de viraje
│   │   ├── nadp_classifier.py            # Clasificación de tipo NADP
│   │   ├── threshold_analysis.py         # Análisis en umbrales (THR 06R, THR 24L)
│   │   └── statistics_generator.py       # Estadísticas (media, varianza, percentil 95, etc.)
│   │
│   ├── geospatial/                 # Transformaciones y análisis geoespaciales
│   │   ├── __init__.py
│   │   ├── coordinate_transform.py # Proyección estereográfica (Translib/geoutils)
│   │   ├── runway_geometry.py      # Definición geométrica de pistas
│   │   ├── geographic_filter.py    # Filtros geográficos para THR y zonas críticas
│   │   └── kml_generator.py        # Generación de archivos KML
│   │
│   ├── database/                   # Gestión de datos persistentes
│   │   ├── __init__.py
│   │   ├── data_manager.py         # Gestor centralizado de Pandas DataFrames
│   │   ├── cache_handler.py        # Caché de datos procesados
│   │   └── csv_export.py           # Exportación de resultados a CSV
│   │
│   ├── api/                        # Endpoints REST y WebSocket
│   │   ├── __init__.py
│   │   ├── routes.py               # Rutas principales (upload, query, filter, export)
│   │   ├── websocket_handler.py    # Gestor de WebSocket (eventos, actualizaciones)
│   │   └── response_formatter.py   # Formateo de respuestas JSON/GeoJSON
│   │
│   └── helpers/                    # Utilidades y funciones auxiliares
│       ├── __init__.py
│       ├── logger.py               # Sistema de logging
│       ├── validators.py           # Validadores (CSV, datos, rangos)
│       ├── constants.py            # Constantes aeronáuticas (separaciones min, etc.)
│       └── errors.py               # Excepciones personalizadas
│
├── frontend/
│   ├── index.html                  # Página principal
│   ├── upload.html                 # Página de carga de archivos
│   ├── analysis.html               # Dashboard de análisis
│   │
│   ├── css/
│   │   ├── styles.css              # Estilos globales
│   │   ├── layout.css              # Layouts y grid
│   │   ├── components.css          # Componentes (botones, modales, etc.)
│   │   ├── table.css               # Estilos de tabla
│   │   ├── map.css                 # Estilos de mapa
│   │   ├── filters.css             # Estilos de filtros
│   │   ├── charts.css              # Estilos de gráficos
│   │   └── responsive.css          # Media queries
│   │
│   ├── js/
│   │   ├── app.js                  # Inicialización general
│   │   ├── websocket.js            # Cliente WebSocket
│   │   ├── api-client.js           # Cliente HTTP/AJAX
│   │   ├── upload-handler.js       # Gestión de carga de archivos
│   │   ├── table-manager.js        # Gestión de tabla de datos
│   │   ├── map-manager.js          # Inicialización y control del mapa
│   │   ├── filters-manager.js      # Lógica de filtros (pista, período, etc.)
│   │   ├── charts-generator.js     # Generación de gráficos
│   │   ├── export-manager.js       # Exportación (CSV, KML)
│   │   ├── utils.js                # Utilidades (formateo, validación, etc.)
│   │   └── config.js               # Configuración del cliente
│   │
│   └── assets/
│       ├── icons/                  # Iconos y SVG
│       ├── images/                 # Imágenes estáticas
│       └── data/                   # Datos estáticos (geometrías de pistas, etc.)
│
├── raw_data/
│   ├── input_csv/                  # CSVs de entrada (ASTERIX + planes de vuelo)
│   ├── processed/                  # Datos procesados (intermedios)
│   └── exports/                    # Archivos exportados (CSV, KML)
│
├── tests/
│   ├── __init__.py
│   ├── test_csv_loader.py
│   ├── test_calculations.py
│   ├── test_geospatial.py
│   └── test_api.py
│
└── docs/
    ├── ARCHITECTURE.md             # Documento de arquitectura detallado
    ├── API_SPECIFICATION.md        # Especificación de endpoints
    ├── DATA_FLOW.md                # Flujo de datos end-to-end
    ├── INSTALLATION.md             # Guía de instalación y setup
    ├── USER_MANUAL.md              # Manual de usuario
    └── CALCULATIONS.md             # Descripción detallada de cálculos
```

---

## 3. ARQUITECTURA DE BACKEND

### 3.1 Flujo de Datos Principal

```
CSV Input (ASTERIX + Flight Plans)
    ↓
[CSV Loader] — Validación de estructura y contenido
    ↓
[Data Validator] — Rango, tipos, campos obligatorios
    ↓
[ASTERIX Handler] — Decodificación y limpieza de datos
    ↓
[Flight Plan Handler] — Carga y relación con ASTERIX
    ↓
[Runway Filter] — Filtro geográfico (24L, 06R)
    ↓
[Interpolation] — Interpolación a 1 segundo
    ↓
[Geospatial Transform] — Proyección estereográfica
    ↓
[Calculations Module] — Separaciones, NADP, estadísticas
    ↓
[Cache & Export] — Almacenamiento, CSV, KML
    ↓
[API Response] — JSON/GeoJSON para frontend
```

### 3.2 Módulos Backend

#### 3.2.1 `data_processing/csv_loader.py`
**Responsabilidad**: Lectura y validación inicial de CSV

```python
class CSVLoader:
    def __init__(self, file_path: str):
        """Carga CSV con validación básica"""
        self.file_path = file_path
        self.dataframe = None
    
    def load(self) -> pd.DataFrame:
        """Lee CSV, maneja encoding y delimitadores"""
        # Detectar delimitador (;, ,, |)
        # Validar columnas esperadas
        # Manejo de tipos de datos
        return self.dataframe
    
    def validate_schema(self) -> dict:
        """Valida estructura según especificación"""
        # Columnas obligatorias: Time, Latitude, Longitude, Altitude, etc.
        # Tipos esperados: float, int, datetime, string
        # Retorna dict con errores/advertencias
```

#### 3.2.2 `data_processing/asterix_handler.py`
**Responsabilidad**: Procesamiento específico de datos ASTERIX (si están incluidos en CSV)

```python
class ASTERIXHandler:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe
    
    def decode_cat048_fields(self):
        """Extrae y decodifica campos CAT048"""
        # Mode 3/A (Transpondedor)
        # FL (Flight Level)
        # TI (Track ID)
        # RHO/THETA (Posición radar)
        # TA (Indicador de track)
        # BP (Presión barométrica)
        # RA (Altitud reportada)
        # etc.
    
    def decode_cat021_fields(self):
        """Extrae y decodifica campos CAT021 (ADSB)"""
        # LAT/LON (Posición directa)
        # FL (Flight Level)
        # Time
        # etc.
    
    def altitude_correction(self, altitude, barometric_pressure, threshold=6000):
        """Corrige altitud < 6000ft según presión barométrica"""
        # Real_Altitude = FL_ModeC + (BP - 1013.25) * 30 ft
        # Maneja cambios de BP
```

#### 3.2.3 `data_processing/flight_plan_handler.py`
**Responsabilidad**: Carga de planes de vuelo y relación con datos radar

```python
class FlightPlanHandler:
    def __init__(self, flight_plan_csv: str):
        """Carga planes de vuelo"""
        self.flight_plans = pd.read_csv(flight_plan_csv, sep=';', decimal=',')
    
    def merge_with_radar_data(self, radar_df: pd.DataFrame) -> pd.DataFrame:
        """Relaciona planes de vuelo con datos radar por:
        - Callsign/Aircraft ID
        - Timestamp cercano
        - Retorna DataFrame merged
        """
    
    def extract_departure_info(self):
        """Extrae info de despegue (runway, SID, etc.)"""
```

#### 3.2.4 `data_processing/runway_filter.py`
**Responsabilidad**: Filtrado geográfico específico por pista

```python
class RunwayFilter:
    def __init__(self):
        # Define geometría de pistas (24L, 06R)
        # Umbrales (THR)
        # Zonas de aproximación
        self.rwy_24l_geometry = {...}  # Lat/Lon bounds, orientación
        self.rwy_06r_geometry = {...}
    
    def filter_by_runway(self, df: pd.DataFrame, runway: str) -> pd.DataFrame:
        """Filtra datos que pertenecen a una pista específica
        Usa filtros geográficos (centroide, ±500m laterales, etc.)
        """
    
    def is_within_threshold(self, lat, lon, runway):
        """Determina si punto está dentro del umbral de pista"""
    
    def is_turning_before_threshold(self, track_data, runway):
        """Detecta si aeronave gira ANTES del umbral"""
```

#### 3.2.5 `data_processing/interpolation.py`
**Responsabilidad**: Interpolación de datos a 1 segundo

```python
class DataInterpolator:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe
    
    def interpolate_to_1_second(self, group_by: str = 'aircraft_id') -> pd.DataFrame:
        """Interpola datos a 1 segundo:
        - Linear para posición (Lat, Lon)
        - Linear para altitud
        - Linear para velocidad (IAS)
        - Preserva valores discretos (Mode 3/A, tipo aeronave)
        """
        # Por cada aeronave:
        # - Encontrar timestamps originales
        # - Generar serie temporal 1Hz
        # - Interpolar campos continuos
        # - Forward-fill campos discretos
```

#### 3.2.6 `geospatial/coordinate_transform.py`
**Responsabilidad**: Proyección a sistema de referencia estereográfica

```python
class CoordinateTransformer:
    def __init__(self, projection='stereographic_bcn'):
        """Inicializa proyección estereográfica según Translib/geoutils"""
        # Centro de proyección: Barcelona airport vicinity
        # Datum: WGS84 → Proyección Mercator/Estereográfica
    
    def wgs84_to_projected(self, lat, lon) -> tuple:
        """Convierte WGS84 (lat/lon) a coordenadas proyectadas (X, Y)"""
        # Usa Translib o equivalente
    
    def projected_to_wgs84(self, x, y) -> tuple:
        """Proyección inversa"""
    
    def calculate_bearing(self, lat1, lon1, lat2, lon2) -> float:
        """Calcula rumbo entre dos puntos"""
    
    def calculate_distance(self, lat1, lon1, lat2, lon2) -> float:
        """Calcula distancia en metros"""
```

#### 3.2.7 `calculations/separation_calculator.py`
**Responsabilidad**: Cálculo de separaciones entre despegues consecutivos

**Teoría de Separación**: 
Las aeronaves en despegue deben mantener separación mínima para evitar riesgo de colisión. Tres criterios coexisten (se aplica el más restrictivo):
- **Radar (2.5 NM / 90s)**: Basado en precisión de posicionamiento SSR
- **Estela (hasta 4 NM / 180s)**: Basado en vórtices del despegue anterior
- **LoA (típicamente 2.0 NM)**: Acuerdo local bajo condiciones específicas

**Método de Cálculo Radar**:
```
Separación = distancia mínima entre trayectorias:
d(t) = √[(x₁(t) - x₂(t))² + (y₁(t) - y₂(t))²]
Cumplimiento: min(d para todo t) ≥ 2.5 NM O tiempo_despegue ≥ 90s
```

```python
class SeparationCalculator:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe
        self.icao_radar_sep_nm = 2.5
        self.icao_radar_sep_sec = 90
    
    def calculate_radar_separation(self, departures_sequence: list) -> dict:
        """
        Calcula separación mínima radar entre despegues consecutivos.
        
        Retorna:
        {
          'pairs': [{from_ac, to_ac, min_radar_sep_nm, compliant, margin_nm}, ...],
          'statistics': {avg, percentile_95, compliance_pct, critical_pairs}
        }
        
        Algoritmo:
        1. Para cada par de despegues (i, i+1)
        2. Extraer trayectorias interpoladas a 1 segundo
        3. Calcular distancia euclidiana en coordenadas proyectadas
        4. Identificar separación mínima en toda la secuencia
        5. Validar contra regla 2.5NM / 90s (lo que sea mayor)
        """
        results = {'pairs': [], 'statistics': {}, 'critical_pairs': []}
        
        for i in range(len(departures_sequence) - 1):
            ac1 = departures_sequence[i]
            ac2 = departures_sequence[i + 1]
            
            # Alinear timestamps comunes
            common_times = intersection(ac1['times'], ac2['times'])
            separations = []
            
            for t in common_times:
                pos1 = ac1['positions'][t]
                pos2 = ac2['positions'][t]
                
                # Distancia euclidiana: √[(Δx)² + (Δy)²]
                d_h_m = sqrt((pos1['x'] - pos2['x'])**2 + (pos1['y'] - pos2['y'])**2)
                d_h_nm = d_h_m / 1852.0  # Conversión a NM
                separations.append({'time': t, 'distance_nm': d_h_nm})
            
            if not separations:
                continue
            
            min_sep = min(s['distance_nm'] for s in separations)
            time_diff_sec = (ac2['takeoff_time'] - ac1['takeoff_time']).total_seconds()
            compliant = (min_sep >= self.icao_radar_sep_nm) or (time_diff_sec >= self.icao_radar_sep_sec)
            
            pair_result = {
                'from_ac': ac1['aircraft_id'],
                'to_ac': ac2['aircraft_id'],
                'min_radar_sep_nm': round(min_sep, 3),
                'time_diff_sec': time_diff_sec,
                'compliant': compliant,
                'margin_nm': round(min_sep - self.icao_radar_sep_nm, 3),
                'limiting_factor': 'distance' if min_sep < self.icao_radar_sep_nm else 'time'
            }
            
            results['pairs'].append(pair_result)
            if not compliant:
                results['critical_pairs'].append(pair_result)
        
        if results['pairs']:
            seps = [p['min_radar_sep_nm'] for p in results['pairs']]
            results['statistics'] = {
                'total_pairs': len(results['pairs']),
                'avg_separation_nm': round(mean(seps), 3),
                'percentile_95': round(sorted(seps)[max(0, int(len(seps)*0.95)-1)], 3),
                'min_separation_nm': round(min(seps), 3),
                'max_separation_nm': round(max(seps), 3),
                'compliance_pct': round(
                    (len(results['pairs']) - len(results['critical_pairs'])) 
                    / len(results['pairs']) * 100, 1),
                'critical_count': len(results['critical_pairs'])
            }
        
        return results
    
    def calculate_wake_separation(self, departures_sequence: list, 
                                  wake_rules: dict) -> dict:
        """
        Calcula separación de estela según categoría de aeronave.
        
        Reglas ICAO estándar:
        - Heavy (B777, A380) → Light: 4 NM o 180 segundos
        - Heavy → Medium (B737, A320): 3 NM o 120 segundos
        - Medium → Light: 3 NM o 120 segundos
        - Mismo tipo: 2.5 NM o 90s (regla radar)
        
        La estela es especialmente peligrosa en despegue porque:
        - Aeronave ligera sigue en configuración despegue (baja velocidad)
        - Vórtices descendentes pueden causar pérdida de sustentación
        
        Parámetro wake_rules: Dict con pares categoría → {nm, sec, description}
        """
        results = {'pairs': [], 'violations': [], 'statistics': {}}
        
        for i in range(len(departures_sequence) - 1):
            ac1 = departures_sequence[i]
            ac2 = departures_sequence[i + 1]
            
            cat1 = ac1.get('wake_category', 'Medium')
            cat2 = ac2.get('wake_category', 'Medium')
            pair_key = f"{cat1}->{cat2}"
            
            wake_rule = wake_rules.get(pair_key, {'nm': 2.5, 'sec': 90})
            min_sep_nm = self._calc_min_separation(ac1, ac2)
            time_diff_sec = (ac2['takeoff_time'] - ac1['takeoff_time']).total_seconds()
            
            compliant_dist = min_sep_nm >= wake_rule['nm']
            compliant_time = time_diff_sec >= wake_rule['sec']
            compliant = compliant_dist or compliant_time
            
            pair_result = {
                'from_ac': ac1['aircraft_id'],
                'from_cat': cat1,
                'to_ac': ac2['aircraft_id'],
                'to_cat': cat2,
                'rule_type': pair_key,
                'required_nm': wake_rule['nm'],
                'required_sec': wake_rule['sec'],
                'actual_nm': round(min_sep_nm, 3),
                'actual_sec': time_diff_sec,
                'compliant': compliant,
                'distance_ok': compliant_dist,
                'time_ok': compliant_time
            }
            
            results['pairs'].append(pair_result)
            if not compliant:
                results['violations'].append(pair_result)
        
        if results['pairs']:
            results['statistics'] = {
                'total_pairs': len(results['pairs']),
                'violations': len(results['violations']),
                'compliance_pct': round(
                    (len(results['pairs']) - len(results['violations'])) 
                    / len(results['pairs']) * 100 if results['pairs'] else 0, 1),
                'heavy_to_light_count': sum(1 for p in results['pairs'] 
                                          if p['from_cat'] == 'Heavy' and p['to_cat'] == 'Light')
            }
        
        return results
    
    def calculate_loa_separation(self, departures_sequence: list,
                                loa_rules: dict) -> dict:
        """
        Calcula separación según LoA Barcelona.
        
        LoA (Letter of Agreement) entre Enfoque Barcelona y Operadores
        puede permitir separaciones reducidas bajo condiciones:
        - SID específica (p.ej., BADOK1 o BALMA2)
        - Condiciones meteorológicas (VFR)
        - Tipo de aeronave certificada
        - Horario (peak vs off-peak)
        
        Aplicación: Si ambas aeronaves cumplen criterios LoA, usar 2.0 NM
                    Si no, usar ICAO estándar 2.5 NM
        """
        results = {'pairs': [], 'loa_applicable_count': 0}
        
        for i in range(len(departures_sequence) - 1):
            ac1 = departures_sequence[i]
            ac2 = departures_sequence[i + 1]
            
            loa_applicable = self._check_loa_applicability(ac1, ac2, loa_rules)
            required_sep_nm = loa_rules.get('loa_separation_nm', 2.0) if loa_applicable else 2.5
            
            actual_sep_nm = self._calc_min_separation(ac1, ac2)
            compliant = actual_sep_nm >= required_sep_nm
            
            results['pairs'].append({
                'from_ac': ac1['aircraft_id'],
                'to_ac': ac2['aircraft_id'],
                'loa_applicable': loa_applicable,
                'required_nm': required_sep_nm,
                'actual_nm': round(actual_sep_nm, 3),
                'compliant': compliant,
                'margin_nm': round(actual_sep_nm - required_sep_nm, 3)
            })
            
            if loa_applicable:
                results['loa_applicable_count'] += 1
        
        if results['pairs']:
            results['loa_percentage'] = round(
                results['loa_applicable_count'] / len(results['pairs']) * 100, 1)
        
        return results
    
    def evaluate_separation_compliance(self, actual_sep, min_sep) -> bool:
        """Determina si se cumple la separación mínima"""
        return actual_sep >= min_sep
    
    def _calc_min_separation(self, ac1, ac2) -> float:
        """Calcula separación mínima entre dos aeronaves en toda su trayectoria"""
        # Implementación interna
        pass
    
    def _check_loa_applicability(self, ac1, ac2, loa_rules) -> bool:
        """Verifica si ambas aeronaves cumplen criterios LoA"""
        # Implementación interna
        pass
```

#### 3.2.8 `calculations/nadp_classifier.py`
**Responsabilidad**: Clasificación de tipo NADP (Noise Abatement Departure Procedure)

**Teoría de NADP**:
NADP = procedimientos para minimizar impacto sonoro en comunidades adyacentes. Barcelona tiene:
- **NADP 1** (Perfil reducido): Despegue potencia reducida, aceleración lenta → menor ruido
- **NADP 2** (Perfil estándar): Despegue potencia completa, SID estándar
- **NADP 3** (Perfil alto): Despegue potencia completa + ascenso rápido → altitud rápido

Clasificación se realiza mediante **indicadores aerodinámicos** (IAS a altitudes concretas):
```
SI (IAS a 3000ft) ∈ [150, 170] kts  →  NADP 1 (reducido)
SI (IAS a 3000ft) ∈ [170, 200] kts  →  NADP 2 (estándar)
SI (IAS a 3000ft) > 200 kts         →  NADP 3 (alto)

Alternativa: Interpolación lineal en rango observado
```

**Algoritmo de Extracción de IAS a Altitud**:
1. Encontrar punto de track donde altitud ≈ target_altitude (±tolerance)
2. Si exacto no existe, interpolar IAS entre dos puntos adyacentes
3. Retornar IAS interpolada

```python
class NADPClassifier:
    def __init__(self):
        """
        Define criterios NADP según especificación Barcelona.
        
        Criterios típicos (pueden variar según actualización Barcelona):
        """
        self.nadp_types = ['NADP1', 'NADP2', 'NADP3']
        
        # Definición de criterios: IAS a altitudes específicas
        self.ias_criteria = {
            'NADP1': {
                'altitude_1_ft': 1000,
                'ias_1_min': 120,
                'ias_1_max': 150,
                'altitude_2_ft': 3000,
                'ias_2_min': 150,
                'ias_2_max': 170,
                'description': 'Reduced power, slow acceleration'
            },
            'NADP2': {
                'altitude_1_ft': 1500,
                'ias_1_min': 150,
                'ias_1_max': 180,
                'altitude_2_ft': 3000,
                'ias_2_min': 170,
                'ias_2_max': 200,
                'description': 'Standard departure profile'
            },
            'NADP3': {
                'altitude_1_ft': 1500,
                'ias_1_min': 180,
                'ias_1_max': 210,
                'altitude_2_ft': 3000,
                'ias_2_min': 200,
                'ias_2_max': 250,
                'description': 'High performance, rapid climb'
            }
        }
    
    def classify_departure(self, track_data, departure_time) -> dict:
        """
        Clasifica despegue según indicadores aerodinámicos.
        
        Parámetros:
        - track_data: Trayectoria con {timestamp, altitude_ft, ias_kts, ...}
        - departure_time: Tiempo de despegue
        
        Retorna:
        {
          'nadp_type': 'NADP1' | 'NADP2' | 'NADP3' | 'UNCLASSIFIED',
          'confidence': 0.95,  # Cuán segura es la clasificación
          'ias_at_1000ft': 145,
          'ias_at_3000ft': 165,
          'details': {...}
        }
        
        Algoritmo:
        1. Extraer IAS a altitudes discriminantes (1000ft, 3000ft)
        2. Comparar contra criterios de cada NADP
        3. Determinar mejor coincidencia
        4. Calcular confianza (qué tan cerca de límites)
        """
        result = {
            'nadp_type': 'UNCLASSIFIED',
            'confidence': 0.0,
            'ias_at_1000ft': None,
            'ias_at_3000ft': None
        }
        
        # Extraer IAS a altitudes clave
        ias_1000 = self.extract_ias_at_altitude(track_data, 1000, tolerance=100)
        ias_3000 = self.extract_ias_at_altitude(track_data, 3000, tolerance=100)
        
        result['ias_at_1000ft'] = ias_1000
        result['ias_at_3000ft'] = ias_3000
        
        if ias_3000 is None:
            return result  # No se puede clasificar sin datos a 3000ft
        
        # Comparar contra criterios
        best_match = None
        best_score = -1
        
        for nadp_type, criteria in self.ias_criteria.items():
            # Score basado en qué tan centrado está en rango NADP
            ias_score = self._calculate_nadp_score(
                ias_1000, ias_3000, criteria
            )
            
            if ias_score > best_score:
                best_score = ias_score
                best_match = nadp_type
        
        result['nadp_type'] = best_match if best_match else 'UNCLASSIFIED'
        result['confidence'] = max(0, min(1, best_score / 100))  # Normalizar a [0, 1]
        result['score'] = best_score
        
        return result
    
    def extract_ias_at_altitude(self, track_data, target_altitude_ft, tolerance=100) -> float:
        """
        Extrae IAS cuando aeronave pasa por altitud objetivo.
        
        Parámetros:
        - track_data: Lista de records {timestamp, altitude_ft, ias_kts, ...}
        - target_altitude_ft: Altitud objetivo (feet)
        - tolerance: Tolerancia en altitud (feet) para búsqueda
        
        Retorna: IAS interpolada en target_altitude, o None si no encontrado
        
        Algoritmo:
        1. Buscar puntos donde altitud esté en [target - tolerance, target + tolerance]
        2. Si encuentra exacto, retornar IAS
        3. Si no, interpolar entre dos puntos adyacentes
        """
        # Filtrar puntos dentro de rango de tolerancia
        candidates = [
            t for t in track_data 
            if abs(t['altitude_ft'] - target_altitude_ft) <= tolerance
        ]
        
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return candidates[0]['ias_kts']
        
        # Si múltiples candidatos, retornar el más cercano (o interpolar)
        closest = min(candidates, key=lambda t: abs(t['altitude_ft'] - target_altitude_ft))
        return closest['ias_kts']
    
    def _calculate_nadp_score(self, ias_1000, ias_3000, criteria) -> float:
        """
        Calcula puntuación de coincidencia con criterio NADP.
        
        Puntuación: 100 = coincidencia perfecta, 0 = no coincide
        Factores:
        - Qué tan centrado está en rango (si está en centro = 100)
        - Si está fuera de rango = penalización proporción
        """
        if ias_3000 is None:
            return -1
        
        # Rango esperado para 3000ft
        min_ias = criteria['ias_2_min']
        max_ias = criteria['ias_2_max']
        range_width = max_ias - min_ias
        center_ias = (min_ias + max_ias) / 2
        
        # Distancia desde centro
        distance_from_center = abs(ias_3000 - center_ias)
        
        if distance_from_center > range_width / 2:
            # Fuera de rango
            return -1 * distance_from_center
        
        # Dentro de rango: score inversamente proporcional a distancia
        return 100 - (distance_from_center / range_width * 100)
```

#### 3.2.9 `calculations/statistics_generator.py`
**Responsabilidad**: Cálculo de estadísticas agregadas y análisis distribucional

**Teoría Estadística**:
Las estadísticas descriptivas permiten **resumir y comunicar** patrones en datos de separación:
- **Media**: Tendencia central (suma / cantidad)
- **Mediana**: Punto central (robusto a outliers, divide distribución en 50-50)
- **Desviación estándar**: Dispersión alrededor de media (σ)
- **Percentil 95**: Valor por debajo del cual cae 95% de datos
  - En aeronáutica es crítico: "El 95% de separaciones > 2.7 NM"
  - Indica margen de seguridad operacional
- **Skewness**: Asimetría (negativo = cola izquierda, positivo = cola derecha)

```python
class StatisticsGenerator:
    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe
    
    def calculate_separation_statistics(self, separations_list: list) -> dict:
        """
        Calcula estadísticas descriptivas para separaciones.
        
        Parámetros:
        - separations_list: Lista de valores de separación (en NM)
        
        Retorna:
        {\n          'mean': 3.12,\n          'median': 3.05,\n          'std_dev': 0.85,\n          'percentile_95': 4.2,\n          'min': 1.8,\n          'max': 6.5,\n          'violations_count': 3,\n          'violations_pct': 5.2,\n          'distribution_shape': 'Normal'\n        }\n        \n        Fórmulas:\n        - Mean: μ = Σx / n\n        - Median: Valor central en data ordenada\n        - StdDev: σ = √[Σ(x - μ)² / n]\n        - Percentile 95: P(X ≤ p95) = 0.95\n        \"\"\"\n        if not separations_list:\n            return {}\n        \n        separations_array = np.array(separations_list)\n        \n        result = {\n            'count': len(separations_list),\n            'mean': round(float(np.mean(separations_array)), 3),\n            'median': round(float(np.median(separations_array)), 3),\n            'std_dev': round(float(np.std(separations_array)), 3),\n            'variance': round(float(np.var(separations_array)), 3),\n            'min': round(float(np.min(separations_array)), 3),\n            'max': round(float(np.max(separations_array)), 3),\n            'percentile_5': round(float(np.percentile(separations_array, 5)), 3),\n            'percentile_25': round(float(np.percentile(separations_array, 25)), 3),\n            'percentile_75': round(float(np.percentile(separations_array, 75)), 3),\n            'percentile_95': round(float(np.percentile(separations_array, 95)), 3),\n        }\n        \n        # Skewness y kurtosis para caracterizar forma distribución\n        from scipy import stats\n        result['skewness'] = round(float(stats.skew(separations_array)), 3)\n        result['kurtosis'] = round(float(stats.kurtosis(separations_array)), 3)\n        \n        # Determinar forma distribución\n        if abs(result['skewness']) < 0.5 and abs(result['kurtosis']) < 1:\n            result['distribution_shape'] = 'Approximately Normal'\n        elif result['skewness'] > 0.5:\n            result['distribution_shape'] = 'Right-skewed'\n        elif result['skewness'] < -0.5:\n            result['distribution_shape'] = 'Left-skewed'\n        else:\n            result['distribution_shape'] = 'Symmetric'\n        \n        # Contar violaciones (< 2.5 NM ICAO standard)\n        violations = [s for s in separations_list if s < 2.5]\n        result['violations_count'] = len(violations)\n        result['violations_pct'] = round(len(violations) / len(separations_list) * 100, 1)\n        \n        return result\n    \n    def calculate_turn_statistics(self, turn_data: list) -> dict:\n        \"\"\"\n        Estadísticas sobre posición y altitud del viraje (turning point).\n        \n        Turn Data esperado:\n        [ {aircraft_id, altitude_ft, lat, lon, time}, ... ]\n        \n        Retorna:\n        {\n          'avg_turn_altitude_ft': 1250,\n          'percentile_95_altitude': 1850,\n          'turn_location_spread_nm': 1.2\n        }\n        \"\"\"\n        if not turn_data:\n            return {}\n        \n        altitudes = [t.get('altitude_ft', 0) for t in turn_data]\n        altitudes = [a for a in altitudes if a > 0]\n        \n        result = {\n            'count': len(altitudes),\n            'avg_altitude_ft': round(np.mean(altitudes), 0) if altitudes else None,\n            'median_altitude_ft': round(np.median(altitudes), 0) if altitudes else None,\n            'std_dev_ft': round(np.std(altitudes), 0) if altitudes else None,\n            'percentile_95': round(float(np.percentile(altitudes, 95)), 0) if altitudes else None,\n            'min_altitude_ft': int(np.min(altitudes)) if altitudes else None,\n            'max_altitude_ft': int(np.max(altitudes)) if altitudes else None,\n        }\n        \n        return result\n    \n    def calculate_threshold_statistics(self, threshold_data: dict) -> dict:\n        \"\"\"\n        Estadísticas en umbrales de runway.\n        \n        Threshold Data esperado:\n        {\n          'rwy_24l': [{aircraft_id, altitude_ft, ias_kts}, ...],\n          'rwy_06r': [{...}, ...]\n        }\n        \n        Retorna: Estadísticas separadas por pista\n        \"\"\"\n        results = {}\n        \n        for runway, data in threshold_data.items():\n            altitudes = [d['altitude_ft'] for d in data if 'altitude_ft' in d]\n            speeds = [d['ias_kts'] for d in data if 'ias_kts' in d]\n            \n            results[runway] = {\n                'count': len(data),\n                'avg_altitude_ft': round(np.mean(altitudes), 0) if altitudes else None,\n                'avg_speed_kts': round(np.mean(speeds), 1) if speeds else None,\n                'altitude_std_dev': round(np.std(altitudes), 0) if altitudes else None,\n                'speed_std_dev': round(np.std(speeds), 1) if speeds else None,\n                'altitude_range': [int(np.min(altitudes)), int(np.max(altitudes))] if altitudes else None\n            }\n        \n        return results\n    \n    def generate_histogram_data(self, data_list: list, bins: int = 20, label: str = 'Value') -> dict:\n        \"\"\"\n        Genera datos para histograma.\n        \n        Parámetros:\n        - data_list: Lista de valores numéricos\n        - bins: Número de intervalos (default 20)\n        - label: Etiqueta del eje X\n        \n        Retorna:\n        {\n          'bins': ['0-1', '1-2', '2-3', ...],\n          'frequencies': [5, 12, 18, ...],\n          'cumulative': [5, 17, 35, ...]\n        }\n        \n        Uso: Para visualizar distribución en histograma frontend (Chart.js)\n        \"\"\"\n        if not data_list:\n            return {}\n        \n        hist, bin_edges = np.histogram(data_list, bins=bins)\n        bin_labels = [f\"{bin_edges[i]:.2f}-{bin_edges[i+1]:.2f}\" \n                     for i in range(len(bin_edges)-1)]\n        cumulative = np.cumsum(hist)\n        \n        return {\n            'bins': bin_labels,\n            'frequencies': hist.tolist(),\n            'cumulative': cumulative.tolist(),\n            'label': label\n        }\n    \n    def generate_percentile_data(self, data_list: list) -> dict:\n        \"\"\"\n        Genera datos para gráfico de percentiles.\n        \n        Retorna:\n        {\n          'percentiles': [5, 10, 25, 50, 75, 90, 95],\n          'values': [1.8, 2.0, 2.3, 3.0, 3.8, 4.5, 5.2]\n        }\n        \n        Uso: Para mostrar cómo varían valores a través de distribución\n        \"\"\"\n        if not data_list:\n            return {}\n        \n        percentiles = [5, 10, 25, 50, 75, 90, 95]\n        values = [np.percentile(data_list, p) for p in percentiles]\n        \n        return {\n            'percentiles': percentiles,\n            'values': [round(v, 3) for v in values]\n        }\n```

#### 3.2.10 `api/routes.py`
**Responsabilidad**: Endpoints REST principales

```python
class APIRoutes:
    @app.route('/api/upload', methods=['POST'])
    def upload_csv():
        """
        Carga archivo CSV
        Request: multipart/form-data (file)
        Response: { status, message, file_id, validation_results }
        """
    
    @app.route('/api/process/<file_id>', methods=['POST'])
    def process_data(file_id):
        """
        Procesa datos cargados
        Request: { runway: '24L' | '06R', filters: {...} }
        Response: { status, progress, results_summary }
        Emite eventos WebSocket de progreso
        """
    
    @app.route('/api/results/<file_id>', methods=['GET'])
    def get_results(file_id):
        """
        Obtiene resultados procesados
        Query params: runway, time_range, filters
        Response: { separations, statistics, charts_data }
        """
    
    @app.route('/api/map-data/<file_id>', methods=['GET'])
    def get_map_data(file_id):
        """
        Obtiene datos para mapa (GeoJSON)
        Response: GeoJSON con tracks, waypoints, umbales, etc.
        """
    
    @app.route('/api/export/<file_id>/<format>', methods=['GET'])
    def export_results(file_id, format):
        """
        Exporta resultados
        format: 'csv' | 'kml'
        Response: archivo descargable
        """
```

#### 3.2.11 `api/websocket_handler.py`
**Responsabilidad**: Comunicación en tiempo real vía WebSocket

```python
class WebSocketHandler:
    def __init__(self, app):
        self.app = app
        self.clients = {}  # { client_id: socket }
    
    @app.websocket('/ws/progress/<file_id>')
    def ws_progress(file_id):
        """WebSocket para progreso de procesamiento
        Eventos:
        - processing_started
        - step_completed (e.g., "asterix_decoded", "calculations_done")
        - progress (0-100%)
        - error
        - processing_complete
        """
    
    def broadcast_progress(self, file_id, step, progress):
        """Envía actualización a todos los clientes del archivo"""
    
    @app.websocket('/ws/updates/<file_id>')
    def ws_live_updates(file_id):
        """WebSocket para actualizaciones de datos en tiempo real
        (para análisis interactivo si aplica)
        """
```

---

## 4. ARQUITECTURA DE FRONTEND

### 4.1 Estructura de Páginas

#### 4.1.1 `index.html` — Página Principal
```html
- Header con logo y navegación
- Panel de carga de archivo (drag & drop)
- Selector de pista (24L / 06R)
- Botón "Iniciar Análisis"
- Indicador de estado
```

#### 4.1.2 `analysis.html` — Dashboard Principal
```html
- Barra superior: info del archivo, filtros rápidos, exportar
- Grid 2x2:
  1. TABLA (datos detallados)
  2. MAPA (visualización geoespacial)
  3. GRÁFICOS (estadísticas)
  4. RESUMEN (métricas principales)
- Sidebar (filtros avanzados)
- Console de errores/logs
```

### 4.2 Componentes Clave

#### 4.2.1 Sistema de Tabla (`js/table-manager.js`)

```javascript
class TableManager {
    constructor(container_id) {
        // Inicializa DataTables o Tabulator
        // Columnas esperadas:
        // - Time, Aircraft ID, Callsign
        // - Latitude, Longitude, Altitude
        // - IAS, Track, Vertical Rate
        // - Mode 3/A, Flight Phase
        // - Separation Status (OK / Warning / Critical)
    }
    
    initialize() {
        // Carga datos desde API
        // Configura paginación, búsqueda, ordenamiento
        // Formatea números (decimal coma, miles separador)
    }
    
    apply_filters(filters) {
        // Aplica filtros en tiempo real (runway, time, etc.)
        // Emite evento para actualizar mapa y gráficos
    }
    
    export_csv() {
        // Exporta datos visibles a CSV (; delimiter, , decimal)
    }
    
    highlight_row(aircraft_id) {
        // Resalta fila al interactuar con mapa
    }
}
```

#### 4.2.2 Sistema de Mapa (`js/map-manager.js`)

```javascript
class MapManager {
    constructor(container_id, center = [41.2865, 2.0759]) {
        // Inicializa Leaflet con centro en Barcelona
        this.map = L.map(container_id).setView(center, 12);
        this.layers = {};
    }
    
    initialize_basemap() {
        // OSM, Satellite, etc.
    }
    
    draw_runways() {
        // Dibuja geometría de pistas (24L, 06R)
        // Incluye orientación, umbales, zonas de aproximación
    }
    
    draw_tracks(geojson_data) {
        // Dibuja trayectorias de despegues
        // Color por estado (OK, Warning, Critical)
        // Grosor por tipo NADP
    }
    
    draw_waypoints(data) {
        // Puntos críticos (Turn, Threshold, etc.)
    }
    
    show_separation_circles(aircraft_positions, separations) {
        // Círculos/buffers mostrando separaciones mínimas
    }
    
    on_track_click(aircraft_id) {
        // Emite evento para actualizar tabla y gráficos
    }
}
```

#### 4.2.3 Sistema de Gráficos (`js/charts-generator.js`)

```javascript
class ChartsGenerator {
    constructor(container_id) {
        // Inicializa Chart.js o Plotly
    }
    
    draw_separation_histogram() {
        // Histograma de separaciones observadas
        // Línea de mínimo requerido
    }
    
    draw_altitude_at_turn_distribution() {
        // Distribución de altitudes en viraje
        // Media, percentil 95, mín/máx
    }
    
    draw_ias_by_nadp() {
        // Gráfico de IAS por tipo NADP
        // Box plot o violin plot
    }
    
    draw_compliance_pie() {
        // Pastel: % cumplimiento vs incumplimiento
    }
    
    draw_timeline_chart() {
        // Línea temporal: separaciones a lo largo de 4 horas
    }
    
    update_charts(data) {
        // Actualiza todos los gráficos con datos filtrados
    }
}
```

#### 4.2.4 Sistema de Filtros (`js/filters-manager.js`)

```javascript
class FiltersManager {
    constructor() {
        this.active_filters = {
            runway: null,          // '24L' | '06R' | null (ambas)
            time_range: [null, null], // [start_time, end_time]
            separation_status: null,  // 'OK' | 'WARNING' | 'CRITICAL'
            nadp_type: null,        // 'NADP1' | 'NADP2' | 'NADP3' | null
            aircraft_type: null,    // Heavy, Medium, Light
            altitude_range: [0, 10000], // ft
        }
    }
    
    apply_filters() {
        // Llama API con filtros actuales
        // Actualiza tabla, mapa, gráficos
    }
    
    reset_filters() {
        // Resetea a estado inicial
    }
    
    save_filter_preset() {
        // Guarda combinación de filtros
    }
}
```

#### 4.2.5 Sistema de Exportación (`js/export-manager.js`)

```javascript
class ExportManager {
    export_csv() {
        // Exporta tabla actual a CSV
        // Respeta filtros aplicados
        // Delimiter: ;
        // Decimal separator: ,
    }
    
    export_kml() {
        // Exporta trayectorias a KML
        // Incluye atributos (aircraft, time, altitude, etc.)
        // Compatible con Google Earth, QGIS
    }
    
    export_pdf_report() {
        // (Opcional) Genera reporte PDF con tablas y gráficos
    }
}
```

### 4.3 CSS Structure

```
css/
├── styles.css           # Reset, tipografía, colores
├── layout.css           # Grid, flexbox
├── components.css       # Botones, inputs, modales
├── table.css            # Estilo de tabla DataTables
├── map.css              # Estilo de mapa Leaflet
├── filters.css          # Panel de filtros
├── charts.css           # Estilo de gráficos
└── responsive.css       # Media queries
```

**Consideraciones de Diseño**:
- Paleta de colores: Azul (profesional), Naranja (alerta), Rojo (crítico)
- Tipografía: Roboto / Open Sans
- Responsive: Mobile first, tablets, desktop
- Accesibilidad: WCAG AA mínimo

---

## 5. FLUJO DE DATOS END-TO-END

### 5.1 Secuencia de Uso Típica

```
1. USUARIO CARGA ARCHIVO
   ↓
   [Upload Handler] → POST /api/upload
   ↓
   Backend: Valida CSV, carga en memoria
   Response: { file_id, validation_status }

2. USUARIO SELECCIONA PISTA Y INICIA ANÁLISIS
   ↓
   [Analysis Handler] → POST /api/process/{file_id}
   ↓
   Backend: Inicia procesamiento
   WebSocket: /ws/progress/{file_id} conecta
   ↓
   Secuencia de pasos (con progreso):
   - CSV loading [10%]
   - Data validation [20%]
   - ASTERIX decoding [30%]
   - Flight plan merging [40%]
   - Runway filtering [50%]
   - Interpolation [60%]
   - Coordinate transformation [70%]
   - Separation calculations [80%]
   - Statistics generation [90%]
   - Caching and indexing [100%]

3. USUARIO VE RESULTADOS
   ↓
   [Results Handler] → GET /api/results/{file_id}
   ↓
   Response: 
   {
     separations: [ { time, aircraft_1, aircraft_2, radar_sep, wake_sep, loa_sep } ],
     statistics: { mean, std, p95, min, max },
     charts_data: { ... },
     metadata: { runway, time_range, num_departures }
   }

4. USUARIO INTERACTÚA
   ↓
   - Selecciona filtros
   - Hace click en tabla → Destaca en mapa
   - Hace click en mapa → Destaca en tabla
   - Exporta resultados

5. USUARIO EXPORTA
   ↓
   [Export Handler] → GET /api/export/{file_id}/{format}
   ↓
   Response: archivo CSV o KML descargable
```

### 5.2 Arquitectura de Caché

```
Memoria (RAM):
├── File-level cache
│   ├── raw_dataframe (CSV original)
│   ├── processed_dataframe (después de validación)
│   ├── interpolated_dataframe (después interpolación 1s)
│   ├── projected_dataframe (después proyección)
│   └── results_cache (resultados finales)
│
└── Session-level cache
    ├── filter_results (tabla filtrada actual)
    └── chart_data (datos gráficos precalculados)

CSV Persistent:
├── processed/{file_id}_processed.csv (datos después validación)
├── results/{file_id}_results.csv (resultados finales)
└── exports/{file_id}_{timestamp}.csv (exportación usuario)
```

---

## 6. PATRONES DE ARQUITECTURA TÉCNICA

### 6.1 Patrón Data Pipeline (ETL)

**Extract-Transform-Load** es el patrón fundamental:

```
[Extract]          [Transform]                      [Load]
CSV Input  ──→  Data Cleaning  ──→  Calculations  ──→  Output
              Validation          NADP Class           Cache
              Interpolation       Separations          Results
              Coordinates         Statistics           Export
```

**Ventajas**:
- **Separación de preocupaciones**: Cada etapa es independiente
- **Testabilidad**: Cada módulo se prueba aisladamente
- **Mantenibilidad**: Cambios en una etapa no afectan otras
- **Escalabilidad**: Fácil agregar nuevas transformaciones

**Implementación**:
- Cada módulo (`csv_loader`, `asterix_handler`, `calculations/*`) es una stage
- Input/output estandarizado (Pandas DataFrames)
- Logging en cada etapa para debugging

### 6.2 Patrón Caché Multi-nivel

**Objetivo**: Evitar reprocessamiento costoso manteniendo datos intermedios

```
User Request
    ↓
[Check L1 Cache] — En memoria (session actual)
    ↓ (Miss)
[Check L2 Cache] — Disco (procesado previamente)
    ↓ (Miss)
[Full Processing] — Todas las etapas
    ↓
[Write to L1 & L2] — Actualizar ambos niveles
```

**L1 (Memoria RAM)**:
- Estructura: `{file_id: {raw_df, processed_df, results_df, charts_data}}`
- TTL: Sesión actual (~ 24 horas)
- Ventaja: Ultra-rápido (< 100ms acceso)

**L2 (Disco SSD)**:
- Estructura: `processed/{file_id}_processed.csv`
- TTL: 72 horas (configurable)
- Ventaja: Persistencia entre sesiones

**Estrategia de invalidación**:
- Usuario carga nuevo archivo → Limpiar ambos caches
- Usuario modifica filtros → Solo actualizar datos filtrados (hit L1 frecuente)

### 6.3 Patrón Observer (Eventos)

**Objetivo**: Mantener Frontend sincronizado con Backend sin polling continuo

```
Backend Processing
    ├─→ [Event: Step Completed]
    │        ↓
    │  WebSocket → Frontend
    │        ↓
    │  Update Progress Bar
    │
    ├─→ [Event: Data Ready]
    │        ↓
    │  WebSocket → Frontend
    │        ↓
    │  Refresh Table/Map/Charts
    │
    └─→ [Event: Error]
             ↓
        WebSocket → Frontend
             ↓
        Show Error Banner
```

**Ventajas**:
- **Bajo overhead**: Solo eventos = solo datos que cambiaron
- **Responsividad**: Feedback inmediato al usuario
- **Escalabilidad**: N clientes suscritos al mismo evento

**Implementación**:
- Backend: `python-socketio` emite eventos
- Frontend: `socket.io-client` escucha eventos
- Conectores: `connect()` → `on('progress')` → `on('complete')`

### 6.4 Patrón Repository

**Objetivo**: Abstraer fuente de datos (CSV, BD, API externa) de lógica de negocio

```
Business Logic
    ↓
[Repository Interface]
    ├─→ CSVRepository (actual)
    ├─→ DatabaseRepository (futuro)
    └─→ APIRepository (futuro - datos remotos)
```

**Beneficio**: Si Barcelona provee API en futuro, cambiar solo Repository (sin tocar cálculos)

### 6.5 Patrón Adapter (Coordinación de Componentes)

**Conversión de datos entre capas**:

```
Frontend (JSON con coma decimal: 3,14)
    ↓ [Adapter]
Backend (Python float: 3.14)
    ↓ [Adapter]
Export (CSV con coma decimal: 3,14)
```

**Implementación**:
- Formatters en API responses
- Parsers en file upload handlers
- Converters en export managers

---

## 6.6 Patrón Strategy (Interpolación)

**Objetivo**: Múltiples estrategias de interpolación según contexto

```
Data Received (4-8 segundo intervals)
    ↓
[Interpolation Strategy]
    ├─→ Linear (para posición, velocidad)
    ├─→ Forward-Fill (para campos discretos: SID, NADP, etc.)
    └─→ Spline (futuro: para trayectorias suaves)
```

**Algoritmo de Interpolación Lineal**:
```
Para cada intervalo [t_i, t_{i+1}]:
  Para cada segundo t ∈ [t_i, t_{i+1}):
    x(t) = x_i + (x_{i+1} - x_i) * (t - t_i) / (t_{i+1} - t_i)
    y(t) = y_i + (y_{i+1} - y_i) * (t - t_i) / (t_{i+1} - t_i)
    alt(t) = alt_i + (alt_{i+1} - alt_i) * (t - t_i) / (t_{i+1} - t_i)
    
Justificación: 
- Posición cambia suavemente (trayectoria continua)
- Velocidad también aproximadamente lineal en intervalos cortos
- Error introduced es < ±3% en trayectoria (aceptable para análisis estadístico)
```

**Forward-Fill para campos discretos**:
```
SID, NADP, Aircraft Type son constantes durante despegue
    ↓
Cuando se interpola tiempo t, usar último valor conocido (no cambiar mid-flight)
```

---

## 7. ESPECIFICACIÓN DE API

**Arquitectura RESTful**:
- **REST** (Representational State Transfer) utiliza acciones HTTP estándar sobre recursos
- **Stateless**: Cada request es independiente; servidor no guarda contexto entre requests
- **Cacheable**: Responses pueden ser cacheadas según headers HTTP
- **Escalable**: Fácil de distribuir en múltiples servidores

**Convenciones aplicadas**:
- **POST**: Crear recurso (procesar datos)
- **GET**: Consultar recurso (obtener resultados)
- **PUT/PATCH**: Actualizar (no usado en v1)
- **DELETE**: Eliminar (no usado en v1)

**Status codes**:
- `200`: OK - éxito
- `202`: Accepted - procesamiento iniciado asincronamente
- `400`: Bad Request - datos inválidos
- `500`: Server Error - fallo interno

### 7.1 POST /api/upload
**Carga archivo CSV**

**Objetivo**: Validar estructura CSV y retornar file_id para procesamiento

```
Request:
- Method: POST
- Content-Type: multipart/form-data
- Body: { file: <CSV file max 500MB> }

Response (200):
{
  "file_id": "abc123def456",
  "filename": "data_20260501.csv",
  "rows": 50000,
  "columns": ["Time", "Latitude", "Longitude", ...],
  "validation": {
    "status": "OK" | "WARNING" | "ERROR",
    "messages": [ "..." ]
  }
}


Response (400):
{
  "error": "Invalid file format",
  "details": "..."
}
```

### 7.2 POST /api/process/{file_id}
**Inicia procesamiento de datos**

```
Request:
- Method: POST
- Body: {
    "runway": "24L" | "06R",
    "filters": {
      "time_range": ["HH:MM:SS", "HH:MM:SS"],
      "aircraft_types": ["Heavy", "Medium", "Light"]
    },
    "options": {
      "generate_kml": true,
      "interpolation_hz": 1
    }
  }

Response (202 Accepted):
{
  "file_id": "abc123def456",
  "status": "processing",
  "websocket_url": "ws://localhost:8000/ws/progress/abc123def456"
}

WebSocket Events:
- { "event": "processing_started", "timestamp": "..." }
- { "event": "step_completed", "step": "asterix_decoded", "progress": 30 }
- { "event": "processing_complete", "results_url": "/api/results/abc123def456" }
- { "event": "error", "message": "..." }
```

### 7.3 GET /api/results/{file_id}
**Obtiene resultados procesados**

```
Request:
- Method: GET
- Query params: 
  - runway (opcional): "24L" | "06R"
  - filters (opcional): JSON encoded filters

Response (200):
{
  "file_id": "abc123def456",
  "runway": "24L",
  "timestamp": "2026-05-01T12:00:00Z",
  
  "summary": {
    "num_departures": 187,
    "time_period": ["06:00:00", "10:00:00"],
    "separations_compliant": 94.5,      // %
    "separations_violation": 5.5        // %
  },
  
  "separations": [
    {
      "departure_sequence": 1,
      "aircraft_1": "EC-ABC",
      "aircraft_2": "EC-DEF",
      "time_separation": 85,            // segundos
      "separation_radar": 2500,         // metros
      "separation_wake": 3000,          // metros (si aplica)
      "separation_loa": 2800,           // metros (si aplica)
      "min_required": 2500,
      "status": "OK" | "WARNING" | "VIOLATION"
    },
    ...
  ],
  
  "statistics": {
    "separation": {
      "mean": 120,
      "std": 25,
      "p95": 175,
      "min": 45,
      "max": 320
    },
    "altitude_at_turn": {
      "mean": 2850,
      "std": 450,
      "p95": 3800,
      "min": 1200,
      "max": 5600
    },
    "nadp_distribution": {
      "NADP1": 45,
      "NADP2": 35,
      "NADP3": 20
    }
  },
  
  "charts_data": {
    "separation_histogram": { ... },
    "altitude_distribution": { ... },
    "compliance_pie": { ... }
  }
}
```

### 7.4 GET /api/map-data/{file_id}
**Obtiene datos geoespaciales (GeoJSON)**

```
Response (200):
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "properties": {
        "aircraft_id": "EC-ABC",
        "callsign": "IB1234",
        "departure_index": 1,
        "nadp_type": "NADP1"
      },
      "geometry": {
        "type": "LineString",
        "coordinates": [
          [2.0759, 41.2865, 0],
          [2.0760, 41.2870, 100],
          ...
        ]
      }
    },
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [2.0765, 41.2868]
      },
      "properties": {
        "name": "Runway 24L Threshold",
        "type": "threshold"
      }
    },
    ...
  ]
}
```

### 7.5 GET /api/export/{file_id}/{format}
**Exporta resultados**

```
format: "csv" | "kml"

CSV Response:
- Content-Type: text/csv
- Delimiter: ;
- Decimal: ,
- Columns: [Time, Aircraft, Latitude, Longitude, Altitude, IAS, ...]
- File: results_{file_id}_{timestamp}.csv

KML Response:
- Content-Type: application/vnd.google-earth.kml+xml
- Incluye: Placemarks para cada despegue, LineStrings para tracks
- File: track_{file_id}_{timestamp}.kml
```

---

## 8. SISTEMA DE WEBSOCKET

### 7.1 Eventos de Procesamiento

```
Client → Server:
{
  "action": "connect",
  "file_id": "abc123def456"
}

Server → Client (periódicamente):
{
  "type": "progress",
  "step": "separation_calculations",
  "progress_percent": 80,
  "current_message": "Calculating wake separations...",
  "elapsed_time_seconds": 45
}

Server → Client (en cambios):
{
  "type": "step_completed",
  "step": "asterix_decoded",
  "duration_seconds": 12,
  "timestamp": "2026-05-01T12:00:15Z"
}

Server → Client (final):
{
  "type": "completed",
  "file_id": "abc123def456",
  "total_duration_seconds": 180,
  "results_url": "/api/results/abc123def456"
}

Server → Client (error):
{
  "type": "error",
  "error_code": "INVALID_DATA",
  "message": "Column 'Latitude' not found in CSV",
  "timestamp": "2026-05-01T12:00:20Z"
}
```

### 7.2 Implementación Cliente

```javascript
class WebSocketClient {
    constructor(file_id) {
        this.file_id = file_id;
        this.ws = null;
        this.handlers = {};
    }
    
    connect() {
        this.ws = new WebSocket(`ws://localhost:8000/ws/progress/${this.file_id}`);
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handle_message(message);
        };
    }
    
    handle_message(message) {
        if (message.type === 'progress') {
            // Actualiza barra de progreso
            this.update_progress_bar(message.progress_percent);
            this.update_status_text(message.current_message);
        }
        if (message.type === 'step_completed') {
            // Log paso completado
            console.log(`✓ ${message.step} en ${message.duration_seconds}s`);
        }
        if (message.type === 'completed') {
            // Redirige a página de resultados
            window.location.href = `/analysis.html?file_id=${message.file_id}`;
        }
        if (message.type === 'error') {
            // Muestra error
            show_error_modal(message.message);
        }
    }
}
```

---

## 9. VARIABLES DE CONFIGURACIÓN

### 8.1 `.env` (Backend)

```
# App Config
FLASK_ENV=development
DEBUG=true
SECRET_KEY=your_secret_key_here
PORT=5000

# Data Processing
CSV_ENCODING=utf-8
CSV_DELIMITER=auto
MAX_FILE_SIZE_MB=500
INTERPOLATION_HZ=1

# Runway Geometry (Barcelona)
RWY_24L_HEADING=240
RWY_24L_THRESHOLD_LAT=41.2865
RWY_24L_THRESHOLD_LON=2.0759
RWY_06R_HEADING=60
RWY_06R_THRESHOLD_LAT=41.2870
RWY_06R_THRESHOLD_LON=2.0760

# Separation Rules (meters/seconds)
MIN_RADAR_SEPARATION_M=2500
MIN_RADAR_SEPARATION_S=90
MIN_WAKE_SEPARATION_M=3000
MIN_WAKE_SEPARATION_S=120

# Geospatial
PROJECTION=stereographic_bcn
PROJECTION_CENTER_LAT=41.2865
PROJECTION_CENTER_LON=2.0759

# Caching
CACHE_DIR=./cache/
CACHE_RETENTION_HOURS=24

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log

# Frontend
FRONTEND_PORT=3000
FRONTEND_ORIGIN=http://localhost:3000
```

### 8.2 `js/config.js` (Frontend)

```javascript
const CONFIG = {
    API_BASE_URL: 'http://localhost:5000',
    WEBSOCKET_URL: 'ws://localhost:5000',
    
    MAP: {
        INITIAL_CENTER: [41.2865, 2.0759],
        INITIAL_ZOOM: 12,
        BASEMAP: 'osm'  // 'osm', 'satellite', 'terrain'
    },
    
    TABLE: {
        ROWS_PER_PAGE: 50,
        SORTABLE_COLUMNS: ['Time', 'Aircraft', 'Altitude', ...],
        FILTERABLE_COLUMNS: ['Runway', 'NADP', 'Status', ...]
    },
    
    CHARTS: {
        HISTOGRAM_BINS: 20,
        PERCENTILES: [50, 75, 95, 99],
        COLORS: {
            OK: '#00AA00',
            WARNING: '#FF9900',
            CRITICAL: '#FF0000'
        }
    },
    
    EXPORT: {
        CSV_DELIMITER: ';',
        CSV_DECIMAL: ',',
        DATE_FORMAT: 'YYYY-MM-DD HH:mm:ss'
    }
};
```

---

## 10. INSTALACIÓN Y CONFIGURACIÓN

### 9.1 Requisitos Previos

```
- Python 3.8+
- Node.js 14+ (si usas herramientas frontend)
- pip (gestor paquetes Python)
- virtualenv o conda (gestor de entorno)
```

### 9.2 Backend Setup

```bash
# 1. Clonar o descargar proyecto
cd ATM-Barcelona-RNAV-Analyzer

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar .env
cp .env.example .env
# Editar .env con valores locales

# 5. Inicializar cache/logs
mkdir -p cache logs processed exports

# 6. Ejecutar aplicación
python main.py
# Backend escucha en http://localhost:5000
```

### 9.3 Frontend Setup

```bash
# Si necesitas compilar/minificar (opcional)
# con webpack/vite, etc.

# O simplemente servir con un servidor estático:
# Opción 1: Python built-in
cd frontend
python -m http.server 3000

# Opción 2: Node.js http-server
npm install -g http-server
http-server -p 3000

# Frontend accesible en http://localhost:3000
```

### 9.4 Dependencies (`requirements.txt`)

```
Flask==2.3.0
pandas==2.0.0
numpy==1.24.0
requests==2.31.0
python-dotenv==1.0.0

# Geospatial
shapely==2.0.0
pyproj==3.5.0
geopy==2.3.0

# Data processing
scipy==1.10.0
scikit-learn==1.2.0  # Para estadísticas avanzadas

# WebSocket
python-socketio==5.9.0
python-engineio==4.7.0

# Utilities
Werkzeug==2.3.0
python-dateutil==2.8.2

# Testing (opcional)
pytest==7.4.0
pytest-cov==4.1.0
```

---

## 11. CONSIDERACIONES TÉCNICAS IMPORTANTES

### 11.1 Rendimiento

- **Caché en memoria**: Mantener DataFrames procesados en RAM para evitar re-procesamiento
- **Índices Pandas**: Usar `set_index()` en columnas frecuentes (Time, Aircraft ID)
- **Chunking**: Para archivos > 100MB, procesar en chunks
- **Async I/O**: Usar async/await en operaciones I/O (file reading, API calls)

### 11.2 Robustez

- **Validación de entrada**: Verificar tipos, rangos, formatos antes de procesar
- **Manejo de excepciones**: Try-except en cada módulo crítico
- **Logging exhaustivo**: Registrar todos los pasos del procesamiento
- **Recuperación de errores**: Permitir re-intentar sin perder datos previos

### 11.3 Escalabilidad

- **Base de datos**: Considera pasar a SQLite o PostgreSQL si necesitas > 1GB datos
- **Procesamiento en background**: Usar Celery si requieres múltiples análisis simultáneos
- **Caching distribuido**: Redis para caché compartido en arquitectura escalada

### 11.4 Seguridad

- **Validación de CSV**: No asumir estructura, validar columnas y tipos
- **Límites de tamaño**: Restringir tamaño máximo de archivo subido
- **Sanitización**: Limpiar caracteres especiales en nombres de archivo
- **Permisos**: Si agregas autenticación en futuro, validar acceso a archivos

### 11.5 Usabilidad

- **Feedback visual**: Mostrar progreso, errores, confirmaciones
- **Mensajes claros**: Descripciones en español de estados y errores
- **Atajos teclado**: Implementar teclas rápidas para acciones frecuentes
- **Responsive design**: Funcional en mobile, tablet, desktop

### 11.6 Manejo de Errores & Recuperación

**Estrategia de Errores en Capas**:

```
User Input
    ↓
[Frontend Validation] — Tipos, rangos, formatos
    ↓ (Error → Show banner, no enviar)
Backend
    ↓
[CSV Schema Validation] — Estructura, columnas obligatorias
    ↓ (Error → Log, return 400)
[Data Type Validation] — Conversión a tipos correctos
    ↓ (Error → Convert o skip row, log warning)
[Business Logic Validation] — Rangos aeronáuticos, coherencia
    ↓ (Error → Flag como anomalía, continuar)
Results
    ↓
[Output Validation] — NaN, infinitos, outliers
    ↓
Response to Client
```

**Patrones de Recuperación**:

1. **Fail-fast para errores críticos**:
   - Archivo corrupto, estructura inválida → Detener inmediatamente
   - Mensaje claro al usuario
   - Permitir reintento con archivo correcto

2. **Partial Success para errores no-críticos**:
   - Algunas filas con datos corruptos → Saltarlas, continuar
   - Log de cuántas filas fueron saltadas
   - Mostrar warning al usuario pero permitir análisis con datos restantes

3. **Graceful Degradation**:
   - Campo opcional falta → Usar valor por defecto
   - Cálculo falla para una aeronave → Omitirla, continuar con otras
   - Interpolación no posible → Usar último valor conocido

4. **Circuit Breaker Pattern** (para escalado futuro):
   ```
   Request → [Circuit Breaker]
       ↓
   [Closed] → Normal processing
   [Open] → Return cached response or error
   [Half-Open] → Test if service recovered
   ```

**Ejemplos de Manejo**:

```python
class RobustCalculator:
    def calculate_separation_safe(self, ac1, ac2):
        \"\"\"Calcula separación con recuperación de errores\"\"\"
        try:
            # Validar entrada
            if not ac1 or not ac2:
                raise ValueError("Missing aircraft data")
            
            # Intentar cálculo
            sep = self.calculate_separation(ac1, ac2)
            
            # Validar resultado
            if sep is None or sep < 0:
                self.logger.warning(f"Invalid separation: {sep}, using default")
                return 2.5  # Separación por defecto conservadora
            
            return sep
            
        except Exception as e:
            self.logger.error(f"Separation calculation failed: {e}")
            # Retornar resultado parcial o valor por defecto
            return None  # Indicar que este par no pudo procesarse
    
    def process_departures_resilient(self, departures):
        \"\"\"Procesa aeronaves ignorando fallos individuales\"\"\"
        results = []
        failed = []
        
        for dep in departures:
            try:
                result = self.analyze_departure(dep)
                results.append(result)
            except Exception as e:
                self.logger.warning(f"Failed to analyze {dep['id']}: {e}")
                failed.append({
                    'aircraft_id': dep['id'],
                    'error': str(e)
                })
        
        return {
            'successful': len(results),
            'failed': len(failed),
            'results': results,
            'errors': failed
        }
```

**Logging & Monitoring**:
- **DEBUG**: Valores intermedios durante cálculos
- **INFO**: Hitos principales (upload complete, processing started, etc.)
- **WARNING**: Datos anómalos, saltos de filas, valores por defecto
- **ERROR**: Fallos críticos, excepciones
- **CRITICAL**: Sistema no recuperable

**Testing de Robustez**:
- CSV con columnas faltantes
- CSV con tipos incorrectos
- CSV con valores extremos (NaN, infinito, negativo)
- CSV vacío
- Archivos mal formados (encoding incorrecto)
- Procesamiento interrumpido (simular timeout)

---

## 12. TIMELINE Y FASES DE IMPLEMENTACIÓN

### Fase 1: Fundación Backend (Semana 1-2)
- [ ] Estructura de carpetas y proyecto base
- [ ] CSV Loader y validación
- [ ] Módulo de ASTERIX Handler
- [ ] Flight Plan Merger

### Fase 2: Cálculos Aeronáuticos (Semana 2-3)
- [ ] Runway Filter y geometría de pistas
- [ ] Separation Calculator (radar, wake, LoA)
- [ ] Turn Detection y NADP Classifier
- [ ] Interpolation a 1 segundo

### Fase 3: Frontend UI (Semana 3-4)
- [ ] Estructura HTML y CSS base
- [ ] Sistema de tabla
- [ ] Sistema de mapa
- [ ] Sistema de filtros

### Fase 4: API y WebSocket (Semana 4)
- [ ] Endpoints REST
- [ ] WebSocket de progreso
- [ ] Integración backend-frontend

### Fase 5: Exportación y Estadísticas (Semana 5)
- [ ] Generador de gráficos
- [ ] Exportación CSV/KML
- [ ] Estadísticas agregadas

### Fase 6: Testing y Documentación (Semana 5-6)
- [ ] Tests unitarios
- [ ] Tests de integración
- [ ] Documentación técnica
- [ ] Manual de usuario

---

## 13. CHECKLIST DE VALIDACIÓN

### Backend
- [ ] CSV carga correctamente con diferentes delimitadores
- [ ] Datos ASTERIX se decodifican correctamente
- [ ] Planes de vuelo se relacionan con datos radar
- [ ] Filtrado por pista funciona (24L, 06R)
- [ ] Interpolación a 1Hz mantiene integridad de datos
- [ ] Proyección estereográfica es precisa
- [ ] Separaciones calculadas son correctas
- [ ] Estadísticas son consistentes
- [ ] WebSocket actualiza en tiempo real
- [ ] Exportación CSV respeta formato (`;`, `,`)
- [ ] Exportación KML es válida y visualizable

### Frontend
- [ ] Interfaz es intuitiva y responsive
- [ ] Tabla filtra y ordena sin lag
- [ ] Mapa carga y es interactivo
- [ ] Gráficos renderizan correctamente
- [ ] Filtros aplican en tiempo real
- [ ] Exportación funciona para CSV y KML
- [ ] Manejo de errores es claro para usuario
- [ ] Performance es aceptable (< 3s carga inicial)

---

## 14. REFERENCIAS Y RECURSOS

- **Leaflet.js Documentation**: https://leafletjs.com/
- **DataTables**: https://datatables.net/
- **Chart.js**: https://www.chartjs.org/
- **Pandas Documentation**: https://pandas.pydata.org/docs/
- **Flask Documentation**: https://flask.palletsprojects.com/
- **KML Specification**: https://developers.google.com/kml/documentation
- **WGS84 and Projections**: https://en.wikipedia.org/wiki/World_Geodetic_System
- **Barcelona Airport Coordinates**: LAT 41.2865, LON 2.0759

---

## 15. PRÓXIMOS PASOS

1. **Feedback del usuario** en este blueprint
2. **Creación de proyecto base** con estructura de carpetas
3. **Configuración de entorno** (venv, .env, dependencias)
4. **Implementación iterativa** siguiendo fases
5. **Testing y validación** contra requisitos
6. **Documentación detallada** de módulos específicos
7. **Entrega de prototipo funcional**

---

**Documento preparado como blueprint arquitectónico.**  
**Contiene especificaciones suficientes para desarrollar sin ambigüedades.**  
**Revisa, comenta, y solicita ajustes o aclaraciones antes de iniciar implementación.**
