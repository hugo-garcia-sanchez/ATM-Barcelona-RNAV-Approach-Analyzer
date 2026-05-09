# 📋 ATM Analyzer P3 — Plan de trabajo

## 🎯 Objetivo del proyecto (rúbrica /10)

| Bloque | Pts | Estado |
|---|---|---|
| Calidad SW (robusto, ampliable, RAM, UX) | 1 | 🟢 base sólida |
| **Datos** (Asterix 4h, filtros, QNH, estereográfica, planes vuelo, tablas estela/LoA, filtros THR, interpolación 1s, viraje 24L, NADP) | **3** | 🟡 ~40 % |
| **Resultados** (separaciones radar/estela/LoA + %, estadísticas, gráficos, viraje, NADP, alt/IAS THR, % giro antes THR) | **4** | 🔴 0 % |
| Extra: 1 día completo de Asterix | 1 | 🔴 falta CSV de 24 h |
| Documentación (memoria, flow SW, dashboard, valoración) | 1 | 🔴 0 % |

---

## 🗺️ Workflow priorizado (orden de ejecución)

### ✅ Orden 0 — YA HECHO
- Pipeline ASTERIX: filtros geo (40.9–41.7 N / 1.5–2.6 E), airborne, FL, QNH (`FL*100 + (BP-1013.25)*30`), techo 6000 ft → `asterix_processor.py`
- Proyección estereográfica con tangencia TMA (41°06'56.560"N 1°41'33.010"E, R=6.368.942,808 m) → `coordinate_transform.py`
- Carga CSV + merge con plan de vuelo por callsign → `flight_plan_loader.py`
- UI básica: mapa Leaflet, tabla paginada, filtros simples, WebSocket
- Persistencia SQLite + endpoints FastAPI

### ✅ Orden 1 — Ampliar modelo de datos (IMPLEMENTADO)
**Problema:** la API solo expone 7 campos; RA, TTA, IAS, BP, GS, IVV, HDG, mode3A, target_address quedan ocultos.
- [x] Añadir patrones a `ASTERIX_COLUMN_PATTERNS` (ti→callsign, ta→target_address, mode3/a→mode3a, hdg→heading, h(ft)→altitude_raw, gs(kt)→ground_speed_kt)
- [x] Ampliar `DataRecordMVP` en `schemas.py` con todos los campos ASTERIX
- [x] Actualizar `_df_to_mvp_records` para volcarlos
- [x] Verificar con `/api/datasets/mvp/processed` que llegan al frontend

### ✅ Orden 2 — Tablas de referencia (IMPLEMENTADO)
Creado `P3_ATM_Analyzer/services/reference_tables.py` con:
- [x] `WAKE_TWR` — pareja (J/H/M/L) → (NM, segundos), con alias Superpesada/Pesada/Media/Ligera
- [x] `WAKE_TMA` — pareja → NM
- [x] `LOA_TABLE` — clasificación motor (HP/R/LP/NR+/NR/NR-) × misma|distinta SID → NM
- [x] `AIRCRAFT_CLASS` — tipo ICAO → clase motor (default: `R`)
- [x] `SID_FAMILIES_24L` y `SID_FAMILIES_06R` — familias NORTH/EAST/SOUTH para chequeo LoA
- [x] Constantes: `THR_24L`, `THR_06R`, `DVOR_BCN`, `R234_LINE_ENDPOINTS`, `TMA_TANGENT_POINT`, `GEO_BBOX`, `ALT_CEILING_FT`, `RADAR_MIN_NM`, `RADAR_MIN_VERT_FT`, `START_FROM_THR_NM`
- [x] Helpers: `normalize_wake`, `get_wake_separation`, `get_loa_separation`, `classify_aircraft`, `get_sid_family`, `same_sid_family`

### ✅ Orden 3 — Cálculo de separaciones (IMPLEMENTADO, ~2 pts)
Creado `P3_ATM_Analyzer/services/separations.py`:
- [x] `build_departures` agrupa por callsign, ordena por ATOT y filtra 24L/06R
- [x] Punto inicio (`_find_start_index`): primer fix ≥0,5 NM del THR alejándose
- [x] **Radar TWR**: 1 muestra; pérdida si `radar_twr_nm < 3` y `dalt < 1000 ft`
- [x] **Radar TMA**: mínimo del solapamiento temporal de ambas trazas
- [x] **Estela TWR**: tabla `(NM, segundos)` desde `reference_tables.WAKE_TWR`
- [x] **Estela TMA**: tabla solo distancia
- [x] **LoA TWR**: `classify_aircraft` + `same_sid_family`
- [x] Output CSV vía `separations.to_csv(df)` y `?format=csv`
- [x] Endpoint `GET /api/datasets/mvp/separations` (json | csv)

### ✅ Orden 4 — Interpolación a 1 s (IMPLEMENTADO)
Creado `P3_ATM_Analyzer/services/interpolation.py`:
- [x] Lineal 2D para `(x_m, y_m, latitude, longitude)` entre muestras
- [x] Altitud con IVV: `_altitude_from_ivv` integra IVV*Δt/60 entre muestras válidas
- [x] HDG/IAS/TAS/Mach/BP constantes en ventana 4 s (`HOLD_4S_COLS`, ffill+bfill con limit)
- [x] Roll/TTA/GS/TAR constantes en ventana 16 s (`HOLD_16S_COLS`)
- [x] `interpolate_track` (un callsign) e `interpolate_dataset` (todos)

### ✅ Orden 5 — Detección inicio viraje 24L (IMPLEMENTADO, ~1 pt)
Creado `P3_ATM_Analyzer/services/turn_detection.py`:
- [x] Filtra solo despegues 24L
- [x] Detección triple: roll_angle ≥5°, |dHDG/dt| ≥1.5°/s, desviación >8° del rumbo de pista
- [x] Mantenimiento mínimo 3 muestras (1 Hz) para evitar falsos positivos
- [x] Devuelve lat/lon/alt/time/IAS/dist_thr y método de detección
- [x] Comprueba si la traza cruza la radial R-234 desde DVOR BCN (intersección de segmentos)
- [x] Output CSV (`?format=csv`) y endpoint `GET /api/datasets/mvp/turns`

### ✅ Orden 6 — NADP (IMPLEMENTADO, ~0.5 pt)
Creado `P3_ATM_Analyzer/services/nadp.py`:
- [x] Para cada DEP 24L, IAS interpolada al primer cruce ascendente de 800 ft y 3000 ft (QNH)
- [x] ΔIAS = IAS@3000 − IAS@800; umbral configurable (default 30 kt)
- [x] ΔIAS < umbral → NADP1 (acelera tarde) / ΔIAS ≥ umbral → NADP2 (acelera pronto)
- [x] Output CSV (`?format=csv`) y endpoint `GET /api/datasets/mvp/nadp?threshold_kt=...`

### ✅ Orden 7 — Análisis sobre umbrales 24L/06R (IMPLEMENTADO, ~0.5 pt)
Creado `P3_ATM_Analyzer/services/threshold_analysis.py`:
- [x] Filtro geográfico rectangular sobre cada THR (~±0.5 NM)
- [x] Interpolación lineal entre fixes adyacentes para cazar paso por el THR
- [x] IAS, altitud y heading al pasar el umbral
- [x] Flag `turned_before_thr` cruzando con `compute_turns`
- [x] `summary_metrics` con % giro antes del THR por pista
- [x] Output CSV (`?format=csv`) y endpoint `GET /api/datasets/mvp/thresholds`

### ✅ Orden 8 — Estadísticas (IMPLEMENTADO)
Creado `P3_ATM_Analyzer/services/stats.py`:
- [x] `describe`: media, σ, p95, min, max, count
- [x] `violation_rate`: % filas con flag True (radar/wake/LoA losses, etc.)
- [x] Agrupable por SID, aerolínea (3 chars callsign), tipo aeronave, estela, runway
- [x] `compute_stats(dataset, metric, groupby, violation_col)` orquesta los 4 pipelines (separations|turns|nadp|thresholds)
- [x] Endpoint `GET /api/datasets/mvp/stats?dataset=...&metric=...&groupby=...&violation_col=...`

### ✅ Orden 9 — Frontend (gráficos + dashboard) (IMPLEMENTADO)
- [x] Chart.js v4 vía CDN (jsdelivr) — pendiente fallback offline si lo pide rúbrica
- [x] Nueva pestaña **Analysis** en `index.html` con 4 secciones (separations / turns / NADP / thresholds)
- [x] Histograma separaciones radar TWR, barras % incumplimientos (radar/wake TWR/wake TMA/LoA)
- [x] Histograma distancia de inicio de viraje + tabla detallada (callsign/SID/AC/alt/IAS/dist/método/R-234)
- [x] Doughnut NADP1/NADP2 + histograma ΔIAS + tabla; control de threshold ΔIAS reactivo
- [x] Histogramas alt/IAS al pasar THR + summary `% turned-before-THR` por pista
- [x] Botones Export CSV por sección (apuntan a `?format=csv` de cada endpoint)
- [x] `analysis.js` aislado; `api-client.js` ampliado con `getSeparations/getTurns/getNadp/getThresholds/getStats/csvURL`

### Orden 10 — Documentación + Extra
- [ ] Pedir CSV de 24 h al profesor (extra point)
- [ ] Memoria PDF (LaTeX o Word) con pasos
- [ ] Diagrama flow del SW (mermaid o draw.io)
- [ ] Valoración general

---

## 📚 Referencias clave

- **THR 24L (DEP 24L origen):** 41°17'31.99"N 2°06'11.81"E
- **THR 06R (DEP 06R origen):** 41°16'56.32"N 2°04'27.66"E
- **DVOR BCN:** 41°18'25.6"N 2°06'28.1"E
- **R-234 endpoint costa:** 41°16'05.4"N 2°02'00.0"E
- **TMA tangencia:** 41°06'56.560"N 1°41'33.010"E (R=6 368 942,808 m)
- **Radar mínima:** 3 NM y Δalt <1000 ft simultáneos
- **Estela:** ver tablas pág 22–23 PDF
- **LoA:** ver tabla pág 25 PDF
- **NADP1:** acelera tarde (mantener V2 hasta >3000 ft) — Δ IAS pequeño 800→3000
- **NADP2:** acelera pronto (limpia flaps a 800 ft) — Δ IAS grande 800→3000

---

## 📌 Notas

- Stack: FastAPI + Pandas + Vanilla JS + Leaflet
- CSV actual: `P3_04h_08h.csv` (20 767 filas, 29 columnas, 4 h)
- Para ejecutar: `python run.py`

---

## 🚨 INCONSISTENCIAS DETECTADAS (Dashboard Separations)

Durante la revisión inicial de los resultados del Dashboard de "Separations", se han detectado anomalías graves en los cálculos de porcentajes de incumplimiento que deben ser diagnosticadas y corregidas en el backend (`services/separations.py`):

1. **Selección de las 121 parejas:** El criterio es estrictamente cronológico por la misma pista. Esto es correcto y los datos base (histograma de distancias TWR) parecen lógicos.
2. **Error Wake TWR (Estela en Torre) - ~95% de fallos:** El programa reporta 115 fallos de 121 parejas. Esto indica un error lógico crítico. La normativa Wake en zona TWR exige medir el **TIEMPO** (minutos de separación entre despegues), NO la distancia física en millas. Posiblemente el código esté usando tablas de distancia en vez de tablas de tiempo, o aplicando la validación de forma errónea en la foto fija de 0.5 NM.
3. **Error LoA (Carta de Acuerdo) - ~100% de fallos:** El programa reporta 120 fallos de 121. La validación LoA cruza tipo de aeronave y ruta (Misma SID / Distinta SID). Un porcentaje de fallo casi total implica que el backend está calculando mal la distancia, o bien, está fallando al cruzar las categorías de las tablas (ej. considerando que siempre van por la misma ruta o asignando siempre la distancia más restrictiva sin motivo).

**Próximo paso de diagnóstico:** Revisar el archivo `services/separations.py` para corregir la validación del tiempo en *Wake TWR* y arreglar el cruce de tablas en la *LoA*.
