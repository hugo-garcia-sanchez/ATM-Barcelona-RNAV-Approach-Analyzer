# Memoria - Proyecto 3 PGTA ATM Barcelona RNAV

## 1. Objetivo

El programa analiza los despegues reales de LEBL por las pistas 24L y 06R para
comprobar el comportamiento operacional respecto a las SIDs RNAV 1 implantadas
en Barcelona.

Los calculos cubren los bloques pedidos en el enunciado:

- separaciones entre despegues consecutivos por minima radar, estela y LoA;
- posicion, altitud e inicio del viraje para despegues 24L;
- cruce de la radial R-234 desde el DVOR BCN;
- clasificacion NADP para despegues 24L usando IAS a 800 ft y 3000 ft;
- altitud e IAS al cruzar el extremo/cabecera opuesta de pista;
- estadisticas y dashboard con exportacion CSV.

## 2. Entradas usadas

Ficheros cargados desde `data/inputs/`:

- `P3_04h_08h.csv`: datos radar CAT048 ya decodificados, 20 767 filas.
- `P3_DEP_LEBL.xlsx`: planes de vuelo de despegue, 539 filas.
- `Tabla_Clasificacion_aeronaves.xlsx`: clasificacion de aeronaves, 409 tipos.
- `Tabla_misma_SID_24L.xlsx`: familias de SID equivalentes para LoA en 24L.
- `Tabla_misma_SID_06R.xlsx`: familias de SID equivalentes para LoA en 06R.

Durante el arranque se infieren 289 SIDs que venian vacias en `ProcDesp`
buscando el primer fijo SID compatible dentro de la ruta SACTA.

## 3. Arquitectura del programa

El proyecto esta construido como aplicacion local:

- Backend FastAPI en `P3_ATM_Analyzer/app.py`.
- Endpoints principales en `P3_ATM_Analyzer/api/routes/datasets.py`.
- Procesado de CSV, ASTERIX y plan de vuelo en `P3_ATM_Analyzer/data_processing/`.
- Calculos ATM en `P3_ATM_Analyzer/services/`.
- Proyeccion geometrica en `P3_ATM_Analyzer/geospatial/coordinate_transform.py`.
- Frontend web estatico en `frontend/`, servido por FastAPI y embebible con `pywebview`.
- Persistencia basica SQLite para datasets subidos por la parte no-MVP.

El flujo automatico de arranque esta en `P3_ATM_Analyzer/services/bootstrap.py`:

1. Carga tablas de referencia.
2. Carga plan de vuelo e infiere SIDs faltantes.
3. Carga radar.
4. Aplica filtros ASTERIX.
5. Corrige altitud por QNH.
6. Calcula coordenadas estereograficas.
7. Hace merge radar-plan de vuelo.
8. Deja el dataset procesado listo para los endpoints de analisis.

## 4. Tratamiento de datos radar

El CSV se normaliza en `CSVLoader`:

- detecta separador `;`, `,`, `|` o tabulador;
- soporta decimal con coma;
- renombra columnas ASTERIX a nombres canonicos (`callsign`, `fl`, `bp`,
  `roll_angle`, `tta`, `ias`, `heading`, `ivv`, `track_number`, etc.);
- convierte coordenadas, altitudes, velocidades y tiempos a tipos numericos.

Despues `AsterixProcessor` aplica:

- filtro geografico: `40.9 < lat < 41.7` y `1.5 < lon < 2.6`;
- filtro airborne cuando existe `I230 STAT`;
- filtro de FL valido cuando existe `I090 FL`;
- correccion QNH por debajo de 6000 ft:

```text
altitud_QNH_ft = FL * 100 + (BP - 1013.25) * 30
```

- techo de calculo: altitud corregida `<= 6000 ft`.

Resultado del dataset actual:

- filas radar raw: 20 767;
- filas radar tras filtros: 20 679;
- columnas procesadas: 39.

## 5. Proyeccion estereografica

Todas las distancias horizontales se calculan en plano 2D, como pide el
enunciado, usando proyeccion estereografica conforme con:

- punto de tangencia TMA: `41 06 56.560 N`, `001 41 33.010 E`;
- radio esfera conforme: `6 368 942.808 m`.

El programa anade a cada deteccion:

- `x_m`
- `y_m`

La distancia en NM se calcula como distancia euclidea en el plano dividida por
1852.

## 6. Interpolacion a 1 segundo

La interpolacion esta en `services/interpolation.py`.

Reglas aplicadas:

- posicion `(x_m, y_m)` y tambien `lat/lon`: interpolacion lineal temporal;
- altitud: integracion con `IVV` cuando existe:

```text
alt(t+n) = alt(t) + IVV(t) * n / 60
```

- `HDG`, `IAS`, `TAS`, `Mach`, `BP`: se mantienen constantes en ventana de 4 s;
- `RA`, `TTA`, `GS`, `TAR`: se mantienen constantes en ventana de 16 s;
- identificadores y datos de plan de vuelo se propagan por traza.

Esta interpolacion se usa para separaciones TMA, NADP, virajes y paso por
cabeceras.

## 7. Separaciones entre despegues consecutivos

Implementacion: `services/separations.py`.

Primero se construyen despegues por `callsign`, se filtran solo pistas 24L y
06R, y se ordenan cronologicamente por ATOT dentro de cada pista.

El punto inicial de separacion se define como la primera deteccion del avion
que despega a `>= 0.5 NM` del umbral de salida y alejandose de este.

### 7.1 Minima radar

- TWR: se calcula una muestra en la primera deteccion valida del segundo
  despegue respecto al precedente.
- TMA: se calcula la minima distancia durante el solape temporal de ambas
  trazas interpoladas.
- Hay perdida operativa si:

```text
distancia horizontal < 3 NM
y
diferencia de altitud < 1000 ft
```

### 7.2 Estela

Las tablas de estela se han validado visualmente contra las paginas 22 y 23 del
PDF.

TWR usa distancia y tiempo. Combinaciones implementadas:

- Superpesada -> Pesada: 6 NM, 2 min.
- Superpesada -> Media: 7 NM, 3 min.
- Superpesada -> Ligera: 8 NM, 3 min.
- Pesada -> Pesada: 4 NM.
- Pesada -> Media: 5 NM, 2 min.
- Pesada -> Ligera: 6 NM, 2 min.
- Media -> Ligera: 5 NM, 2 min.

TMA usa solo distancia con la misma matriz de NM.

Las combinaciones no listadas no aplican separacion de estela.

### 7.3 LoA

La tabla LoA de la pagina 25 se aplica para zona TWR. Se usa:

- clase del avion precedente;
- clase del avion sucesivo;
- si los dos vuelos pertenecen a la misma familia de SID o no.

Las clases se cargan desde `Tabla_Clasificacion_aeronaves.xlsx`; si un tipo no
aparece, se considera `R` por defecto, como pide el enunciado.

### 7.4 Resultados de separacion

Para el periodo 04:00-08:00:

- despegues analizados: 123;
- parejas consecutivas: 121;
- parejas con TWR computable: 104;
- parejas con TMA computable: 104;
- parejas sin solape temporal o sin posicion del precedente: 17.

Incumplimientos:

| Criterio | Casos |
|---|---:|
| Radar TWR | 0 |
| Radar TMA | 1 |
| Estela TWR | 0 |
| Estela TMA | 0 |
| LoA TWR | 32 |

Estadistica de distancia radar TWR, sobre 104 parejas computables:

| Medida | NM |
|---|---:|
| media | 4.346 |
| mediana | 4.130 |
| desviacion estandar | 1.301 |
| percentil 95 | 6.696 |
| minimo | 2.579 |
| maximo | 10.723 |

Estadistica de minima distancia radar TMA, sobre 104 parejas computables:

| Medida | NM |
|---|---:|
| media | 4.191 |
| mediana | 3.924 |
| desviacion estandar | 1.351 |
| percentil 95 | 6.557 |
| minimo | 0.054 |
| maximo | 10.681 |

## 8. Inicio de viraje 24L y radial R-234

Implementacion: `services/turn_detection.py`.

Solo se analizan salidas 24L. Se recorta la traza desde el punto `>=0.5 NM`
del umbral y se busca el inicio del viraje usando:

- `abs(roll_angle) >= 5 deg`;
- o variacion de rumbo `>= 1.5 deg/s`;
- o desviacion sostenida respecto al rumbo de pista 24L;
- minimo 3 muestras sostenidas a 1 Hz.

Como el roll angle se actualiza cada 16 s, si la deteccion viene por roll se
refina hacia atras con heading en una ventana de 16 s.

Para evitar falsos positivos tardios, la busqueda de inicio de viraje se limita
al tramo inicial:

- altitud `<= 3000 ft`;
- distancia al umbral `<= 6 NM`.

El cruce de la radial R-234 desde DVOR BCN se comprueba con la traza completa
hasta 6000 ft.

Resultados:

- despegues 24L: 96;
- virajes detectados: 94;
- sin inicio de viraje fiable: 2;
- cruces de la radial R-234: 1.

Metodos de deteccion:

- `roll+hdg`: 49;
- `roll`: 45;
- sin deteccion: 2.

Estadistica de altitud de inicio de viraje, sobre 94 virajes:

| Medida | ft |
|---|---:|
| media | 687.818 |
| mediana | 698.686 |
| desviacion estandar | 160.491 |
| percentil 95 | 920.792 |
| minimo | 60.112 |
| maximo | 1061.517 |

Estadistica de distancia al umbral 24L en inicio de viraje:

| Medida | NM |
|---|---:|
| media | 1.718 |
| mediana | 1.763 |
| desviacion estandar | 0.217 |
| percentil 95 | 2.062 |
| minimo | 1.121 |
| maximo | 2.120 |

## 9. NADP en salidas 24L

Implementacion: `services/nadp.py`.

Para cada salida 24L se obtiene la IAS interpolada en:

- 800 ft;
- 3000 ft.

Se calcula:

```text
delta_IAS = IAS_3000ft - IAS_800ft
```

Umbral usado:

```text
30 kt
```

Criterio:

- `delta_IAS < 30 kt`: NADP1, aceleracion tardia;
- `delta_IAS >= 30 kt`: NADP2, aceleracion temprana;
- si falta alguna IAS: sin clasificar.

Resultados:

| Tipo | Vuelos |
|---|---:|
| NADP1 | 9 |
| NADP2 | 80 |
| Sin clasificar | 7 |

Estadistica de `delta_IAS`, sobre 89 vuelos clasificados:

| Medida | kt |
|---|---:|
| media | 54.975 |
| mediana | 57.000 |
| desviacion estandar | 22.775 |
| percentil 95 | 85.023 |
| minimo | -6.000 |
| maximo | 96.000 |

## 10. Altitud e IAS al paso por cabeceras/DER

Implementacion: `services/threshold_analysis.py`.

Para cada despegue se mide el paso por el extremo opuesto de pista:

- DEP 24L: DER 24L, coordenadas de THR 06R.
- DEP 06R: DER 06R, coordenadas de THR 24L.

Se usa un filtro rectangular aproximado de 0.5 NM alrededor del punto. Si un
vuelo no entra en el filtro, igualmente aparece una fila con
`passes_thr_filter=False` para poder contar el porcentaje pedido por la rubrica.

Resultados:

| Pista | Despegues | Pasan filtro | No pasan filtro | % pasan |
|---|---:|---:|---:|---:|
| 24L | 96 | 94 | 2 | 97.92 |
| 06R | 27 | 26 | 1 | 96.30 |

En 24L, 10 vuelos se detectan como virados antes de cruzar el filtro de cabecera
opuesta, es decir, 10.42% de las salidas 24L.

Altitud media al paso:

| Pista | Media ft | Mediana ft | P95 ft |
|---|---:|---:|---:|
| 24L | 422.640 | 398.299 | 670.122 |
| 06R | 453.762 | 398.869 | 710.454 |

IAS media al paso:

| Pista | Media kt | Mediana kt | P95 kt |
|---|---:|---:|---:|
| 24L | 159.553 | 161.000 | 170.000 |
| 06R | 159.731 | 160.593 | 168.806 |

## 11. CSV unico generado

Se ha creado un export unico en:

```text
data/outputs/p3_resultados_combinados.csv
```

Contenido:

- 123 filas, una por despegue 24L/06R;
- 93 columnas;
- datos base del vuelo;
- separacion respecto al precedente de la misma pista (`sep_*`);
- viraje 24L (`turn_*`);
- NADP 24L (`nadp_*`);
- paso por cabecera/DER (`thr_*`).

Las separaciones se asignan al vuelo sucesivo de la pareja. Por tanto, el primer
despegue de cada pista no tiene bloque `sep_*` porque no tiene precedente en la
misma pista dentro del periodo.

## 12. Dashboard y endpoints

Endpoints principales:

- `GET /api/datasets/mvp/separations`
- `GET /api/datasets/mvp/turns`
- `GET /api/datasets/mvp/nadp`
- `GET /api/datasets/mvp/thresholds`
- `GET /api/datasets/mvp/stats`
- `GET /api/datasets/mvp/combined-results`

Todos aceptan `format=csv` cuando aplica.

El frontend tiene una pestana `Analysis` con:

- histograma de separacion radar TWR;
- barras de incumplimientos radar/estela/LoA;
- histograma y tabla de virajes;
- distribucion NADP;
- histogramas de altitud/IAS en cabecera;
- boton `Combined CSV` para descargar el CSV unico.

Nota: Leaflet y Chart.js se cargan por CDN. Para una evaluacion sin internet se
deberian descargar esos assets o abrir el CSV directamente.

## 13. Verificacion realizada

Se ejecuto:

```bash
./venv/bin/pytest -q
```

Resultado:

```text
4 passed
```

Los tests comprueban:

- lectura real del CSV radar;
- mapeo de columnas ASTERIX;
- valores clave de tablas de estela y LoA contra el PDF;
- bootstrap completo;
- generacion de separaciones, thresholds y CSV combinado;
- registro de endpoints FastAPI.

Tambien se regenero el CSV final con:

```bash
./venv/bin/python - <<'PY'
from pathlib import Path
from P3_ATM_Analyzer.services.bootstrap import bootstrap_inputs
from P3_ATM_Analyzer.data_store import get_processed_data
from P3_ATM_Analyzer.services.combined_export import write_combined_csv

bootstrap_inputs()
write_combined_csv(get_processed_data(), Path("data/outputs/p3_resultados_combinados.csv"))
PY
```

## 14. Cumplimiento de la rubrica

### Calidad software

Cumplido:

- backend modular;
- servicios separados por calculo;
- endpoints claros;
- carga automatica de datos;
- CSV combinado;
- tests automatizados.

Pendiente opcional:

- cachear resultados para evitar recomputar todos los pipelines en cada endpoint.

### Datos

Cumplido:

- 4 h de radar;
- filtros ASTERIX;
- QNH;
- proyeccion estereografica;
- merge con plan de vuelo;
- tablas de estela y LoA;
- filtro de cabeceras;
- interpolacion a 1 s;
- solucion coherente para viraje 24L;
- algoritmo NADP.

### Resultados

Cumplido:

- separaciones radar, estela y LoA;
- perdidas operativas por radar/estela;
- estadisticas descriptivas;
- graficos en dashboard;
- virajes 24L;
- NADP;
- altitud e IAS en cabeceras;
- porcentaje de vuelos que no cruzan el filtro de cabecera.

### Extra

No cumplido por falta de datos de 24 h. El programa podria procesarlos si se
proporciona el CSV/ASTERIX correspondiente.

### Documentacion

Cumplido parcialmente con esta memoria y el codigo. Para entrega final conviene
anadir capturas del dashboard y, si se pide expresamente, un diagrama visual del
flujo software.
