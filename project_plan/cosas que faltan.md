# 📋 ATM Analyzer - Lista de Tareas

## Estado General: 🟢 MVP Funcional - Mejoras Pendientes

---

## 🔴 BUGS CRÍTICOS

- [ ] **Bug: Items desaparecen al aplicar filtros**
  - **Descripción:** Cuando aplicas filtros (altitud, callsign), los items de la tabla desaparecen completamente
  - **Impacto:** Alta - Los filtros no funcionan correctamente
  - **Archivos:** `frontend/main.js` - función `applyFilters()`
  - **Prioridad:** 🔴 CRÍTICA
  - **Notas:** Ver si `state.displayRecords` se está limpiando incorrectamente

---

## 🟡 TAREAS DE OPTIMIZACIÓN

### Tabla y Visualización

- [ ] **Arreglar columnas para mejor visualización**
  - **Descripción:** Las 29 columnas están todas visibles pero el scroll horizontal es difícil de usar
  - **Mejoras sugeridas:**
    - Fijar columnas principales (callsign, lat, lon, alt) en la izquierda
    - Hacer scrolleable el resto de columnas
    - O: Mostrar columnas en dos filas (principales + secundarias)
  - **Archivos:** `frontend/styles.css`, `frontend/main.js` - `renderTablePage()`
  - **Prioridad:** 🟡 ALTA

- [ ] **Permitir desplazamiento vertical en la lista**
  - **Descripción:** Con 500 registros por página, la tabla es muy larga
  - **Mejoras sugeridas:**
    - Sticky header (encabezado fijo al hacer scroll)
    - Altura máxima con scroll interno en tbody
    - Indicador de posición actual (ej: "Viendo 1-500 de 20,767")
  - **Archivos:** `frontend/styles.css`
  - **Prioridad:** 🟡 ALTA

---

### Filtros Avanzados

- [ ] **Añadir más filtros**
  - **Filtros sugeridos:**
    - [ ] Rango de velocidad (Speed: min-max)
    - [ ] Tipo de aeronave (aircraft_id, registration)
    - [ ] Modo de vuelo (FL, mode3/a)
    - [ ] Búsqueda por ruta/origen-destino (si disponible)
    - [ ] Rango de hora (Time: HH:MM - HH:MM)
  - **Archivos:** `frontend/main.js`, `frontend/index.html`
  - **Prioridad:** 🟡 MEDIA
  - **Notas:** Implementar checkbox/toggle para activar/desactivar filtros

- [ ] **Mejorar UX de filtros**
  - **Mejoras sugeridas:**
    - Botón "Clear Filters" para resetear todos
    - Vista previa de cuántos registros cumplen filtro (antes de aplicar)
    - Historial de filtros usados recientemente
  - **Archivos:** `frontend/index.html`, `frontend/main.js`
  - **Prioridad:** 🟡 MEDIA

---

## 🟢 TAREAS OPCIONALES (Futuros)

- [ ] **Exportar datos filtrados a CSV**
  - **Descripción:** Permitir descargar solo los registros visibles/filtrados
  - **Prioridad:** 🟢 BAJA

- [ ] **Visualización de estadísticas**
  - **Sugerencias:** Gráficos de altitud/velocidad por callsign
  - **Prioridad:** 🟢 BAJA

- [ ] **Persistencia de datos (base de datos)**
  - **Descripción:** Guardar CSV en DB en lugar de memoria
  - **Prioridad:** 🟢 BAJA

- [ ] **Autenticación y multi-usuario**
  - **Prioridad:** 🟢 MUY BAJA

---

## ✅ COMPLETADO

- ✅ CSV Upload (Con Spanish decimal parsing)
- ✅ Tabla con todas 29 columnas
- ✅ Paginación (500 registros/página)
- ✅ Timestamps válidos (ISO 8601)
- ✅ Mapa Leaflet con markers
- ✅ Filtros básicos (altitud, callsign)
- ✅ Clear Data + Choose File

---

## 📌 NOTAS DE DESARROLLO

- **Stack:** FastAPI + Pandas + Vanilla JS + Leaflet
- **Browser:** Pywebview (desktop window)
- **CSV:** P3_04h_08h.csv (20,767 registros, 29 columnas)
- **Test Coverage:** Verificar en consola (F12) y terminal servidor

---

## 🚀 PRÓXIMA SESIÓN

1. Revisar y arreglar el bug de filtros desapareciendo
2. Mejorar visualización de columnas (sticky header o fixed columns)
3. Implementar filtros adicionales (velocidad, hora, etc.)
4. Optimizar scroll en tabla
