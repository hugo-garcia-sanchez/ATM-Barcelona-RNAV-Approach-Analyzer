# Cosas que faltan - estado actualizado

Actualizado despues de corregir errores, generar `memoria.md` y producir el CSV
unico de resultados.

## Ya queda cubierto

- [x] Lectura de `03PGTA_Proyecto3.pdf` y `03PGTA_Plantilla evaluacion.pdf`.
- [x] Carga de radar 4 h: `P3_04h_08h.csv`.
- [x] Carga de plan de vuelo: `P3_DEP_LEBL.xlsx`.
- [x] Carga de tablas Excel de clasificacion y misma SID.
- [x] Inferencia de SIDs vacias desde ruta SACTA.
- [x] Filtros ASTERIX: geografico, airborne, FL valido y altitud <= 6000 ft.
- [x] Correccion QNH.
- [x] Proyeccion estereografica conforme Translib/geoutils.
- [x] Interpolacion a 1 s.
- [x] Separaciones consecutivas radar, estela y LoA.
- [x] Perdidas operativas por radar/estela con delta altitud < 1000 ft.
- [x] Deteccion de viraje 24L y radial R-234.
- [x] NADP 24L con IAS a 800 ft y 3000 ft.
- [x] Altitud e IAS en cabeceras/DER 24L y 06R.
- [x] Fila tambien para vuelos que no pasan el filtro de cabecera.
- [x] Estadisticas con media, mediana, varianza, desviacion, p95, min y max.
- [x] Dashboard de analisis.
- [x] Endpoint y boton de CSV combinado.
- [x] CSV unico generado: `data/outputs/p3_resultados_combinados.csv`.
- [x] Tests arreglados: `./venv/bin/pytest -q` pasa.
- [x] Memoria creada: `memoria.md`.

## Resultados actuales verificados

- Radar raw: 20 767 filas.
- Radar procesado: 20 679 filas.
- Despegues analizados: 123.
- Despegues 24L: 96.
- Despegues 06R: 27.
- Parejas consecutivas: 121.
- Parejas con separacion TWR/TMA computable: 104.
- Parejas no computables por falta de solape/posicion del precedente: 17.
- Radar TWR losses: 0.
- Radar TMA losses: 1.
- Wake TWR losses: 0.
- Wake TMA losses: 0.
- LoA losses: 32.
- Virajes 24L detectados: 94 de 96.
- Cruces R-234: 1.
- NADP1: 9.
- NADP2: 80.
- NADP sin clasificar: 7.
- Pasos por filtro cabecera/DER: 120 de 123.

## Pendiente real para entrega

- [ ] Preparar capturas del dashboard para la memoria/presentacion.
- [ ] Hacer un diagrama visual del flujo del software si el profesor lo pide
      como entregable separado. La explicacion ya esta en `memoria.md`.
- [ ] Si la evaluacion se hace sin internet, descargar localmente Leaflet y
      Chart.js o entregar el CSV + capturas, porque ahora el dashboard usa CDN.
- [ ] Conseguir datos de 24 h si se quiere optar al punto extra.
- [ ] Revisar manualmente con el profesor si las 17 parejas sin solape deben
      marcarse como "no computable" o si prefiere otro criterio conservador.

## Comandos de validacion

```bash
./venv/bin/pytest -q
```

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
