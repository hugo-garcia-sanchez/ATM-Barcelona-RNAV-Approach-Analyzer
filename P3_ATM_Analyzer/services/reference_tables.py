"""Tablas de referencia para separaciones, LoA, clasificación de aeronaves y
constantes geográficas del análisis ATM en LEBL (Barcelona).

Fuentes:
- PDF P3 (págs. 22–25): tablas de estela y LoA
- PDF P3 (págs. 51, 55, 57, 63): umbrales y geometría
- AIP España LEBL: SIDs RWY 24L / RWY 06R
"""

from __future__ import annotations

from typing import Dict, Tuple, List


# ---------------------------------------------------------------------------
# Categorías ICAO de estela
# ---------------------------------------------------------------------------
# J = Super (A388, A124)
# H = Heavy
# M = Medium
# L = Light
WAKE_CATEGORIES = ("J", "H", "M", "L")

# Alias tolerantes (algunos planes de vuelo usan "S"/"SUPER" o nombres en español)
WAKE_ALIASES: Dict[str, str] = {
    "SUPER": "J",
    "S": "J",
    "SUPERPESADA": "J",
    "HEAVY": "H",
    "PESADA": "H",
    "MEDIUM": "M",
    "MEDIA": "M",
    "LIGHT": "L",
    "LIGERA": "L",
}


def normalize_wake(code: str | None) -> str | None:
    """Normaliza una categoría de estela a J/H/M/L."""
    if not code:
        return None
    c = str(code).strip().upper()
    if c in WAKE_CATEGORIES:
        return c
    return WAKE_ALIASES.get(c)


# ---------------------------------------------------------------------------
# WAKE_TWR — Separación por estela en TWR (despegue): (NM, segundos)
# Clave: (precedente, siguiente)
# Fuente: PDF P3 pág. 22–23 / ICAO Doc 4444
# ---------------------------------------------------------------------------
WAKE_TWR: Dict[Tuple[str, str], Tuple[float, int]] = {
    # Super delante
    ("J", "J"): (4.0, 120),
    ("J", "H"): (6.0, 120),
    ("J", "M"): (7.0, 180),
    ("J", "L"): (8.0, 180),
    # Heavy delante
    ("H", "J"): (0.0, 60),
    ("H", "H"): (4.0, 120),
    ("H", "M"): (5.0, 120),
    ("H", "L"): (6.0, 180),
    # Medium delante
    ("M", "J"): (0.0, 60),
    ("M", "H"): (0.0, 60),
    ("M", "M"): (3.0, 60),
    ("M", "L"): (5.0, 180),
    # Light delante
    ("L", "J"): (0.0, 60),
    ("L", "H"): (0.0, 60),
    ("L", "M"): (0.0, 60),
    ("L", "L"): (3.0, 60),
}


# ---------------------------------------------------------------------------
# WAKE_TMA — Separación por estela en TMA (sólo distancia, NM)
# Fuente: PDF P3 pág. 23 / ICAO Doc 4444
# ---------------------------------------------------------------------------
WAKE_TMA: Dict[Tuple[str, str], float] = {
    ("J", "J"): 4.0,
    ("J", "H"): 6.0,
    ("J", "M"): 7.0,
    ("J", "L"): 8.0,
    ("H", "J"): 0.0,
    ("H", "H"): 4.0,
    ("H", "M"): 5.0,
    ("H", "L"): 6.0,
    ("M", "J"): 0.0,
    ("M", "H"): 0.0,
    ("M", "M"): 3.0,
    ("M", "L"): 5.0,
    ("L", "J"): 0.0,
    ("L", "H"): 0.0,
    ("L", "M"): 0.0,
    ("L", "L"): 3.0,
}


def get_wake_separation(
    leader_wake: str | None,
    follower_wake: str | None,
    phase: str = "TWR",
) -> Tuple[float, int] | float | None:
    """Devuelve la separación de estela aplicable.

    - phase="TWR" → tupla (NM, segundos)
    - phase="TMA" → NM
    """
    a = normalize_wake(leader_wake)
    b = normalize_wake(follower_wake)
    if a is None or b is None:
        return None
    if phase.upper() == "TWR":
        return WAKE_TWR.get((a, b))
    return WAKE_TMA.get((a, b))


# ---------------------------------------------------------------------------
# LOA_TABLE — Letter of Agreement BCN/TMA
# Clasificación motor del precedente vs. siguiente, distinguiendo si comparten
# o no familia de SID. Valor en NM.
# Fuente: PDF P3 pág. 25.
#
# Clases de motor:
#   HP  — High Performance     (jets potentes: A320neo, B738, A321, etc.)
#   R   — Reactor estándar
#   LP  — Low Performance      (regionales jet menores)
#   NR+ — No-Reactor de prestaciones altas (ATR-72, Q400)
#   NR  — No-Reactor estándar  (ATR-42, Dash-8 100/200)
#   NR- — No-Reactor lento     (turbohélices ligeros, GA twin)
# ---------------------------------------------------------------------------
ENGINE_CLASSES = ("HP", "R", "LP", "NR+", "NR", "NR-")

# (precedente, siguiente, "same" | "diff") -> NM
LOA_TABLE: Dict[Tuple[str, str, str], float] = {}


def _fill_loa() -> None:
    # Valores por defecto basados en pág. 25 PDF.
    # "same" = misma familia de SID, "diff" = familias distintas.
    base_same = {
        ("HP", "HP"): 5.0, ("HP", "R"): 5.0,  ("HP", "LP"): 6.0,
        ("HP", "NR+"): 7.0, ("HP", "NR"): 8.0, ("HP", "NR-"): 9.0,

        ("R",  "HP"): 4.0, ("R",  "R"): 5.0,  ("R",  "LP"): 6.0,
        ("R",  "NR+"): 7.0, ("R",  "NR"): 8.0, ("R",  "NR-"): 9.0,

        ("LP", "HP"): 3.0, ("LP", "R"): 4.0,  ("LP", "LP"): 5.0,
        ("LP", "NR+"): 6.0, ("LP", "NR"): 7.0, ("LP", "NR-"): 8.0,

        ("NR+", "HP"): 3.0, ("NR+", "R"): 3.0, ("NR+", "LP"): 4.0,
        ("NR+", "NR+"): 5.0, ("NR+", "NR"): 6.0, ("NR+", "NR-"): 7.0,

        ("NR",  "HP"): 3.0, ("NR",  "R"): 3.0, ("NR",  "LP"): 3.0,
        ("NR",  "NR+"): 4.0, ("NR",  "NR"): 5.0, ("NR",  "NR-"): 6.0,

        ("NR-", "HP"): 3.0, ("NR-", "R"): 3.0, ("NR-", "LP"): 3.0,
        ("NR-", "NR+"): 3.0, ("NR-", "NR"): 4.0, ("NR-", "NR-"): 5.0,
    }
    # Familias distintas: misma estructura pero relajada en 2 NM (mínimo 3 NM radar).
    for (a, b), v in base_same.items():
        LOA_TABLE[(a, b, "same")] = v
        LOA_TABLE[(a, b, "diff")] = max(3.0, v - 2.0)


_fill_loa()


def get_loa_separation(
    leader_class: str,
    follower_class: str,
    same_sid_family: bool,
) -> float | None:
    """Separación LoA aplicable (NM) entre dos despegues consecutivos."""
    key = (leader_class, follower_class, "same" if same_sid_family else "diff")
    return LOA_TABLE.get(key)


# ---------------------------------------------------------------------------
# AIRCRAFT_CLASS — Tipo ICAO → clase motor
# Cualquier tipo no listado se asume "R" (Reactor estándar).
# ---------------------------------------------------------------------------
DEFAULT_ENGINE_CLASS = "R"

AIRCRAFT_CLASS: Dict[str, str] = {
    # High Performance
    "A20N": "HP", "A21N": "HP", "A319": "HP", "A320": "HP", "A321": "HP",
    "B737": "HP", "B738": "HP", "B739": "HP", "B38M": "HP", "B39M": "HP",
    "A332": "HP", "A333": "HP", "A339": "HP", "A359": "HP", "A35K": "HP",
    "B772": "HP", "B773": "HP", "B77W": "HP", "B788": "HP", "B789": "HP",
    "B78X": "HP", "A388": "HP",
    # Reactor estándar
    "A318": "R", "B736": "R", "B752": "R", "B763": "R", "B764": "R",
    "MD82": "R", "MD83": "R", "MD88": "R", "F100": "R",
    "E190": "R", "E195": "R", "E290": "R", "E295": "R",
    "CRJ9": "R", "CRJX": "R",
    # Low Performance
    "E170": "LP", "E175": "LP", "CRJ7": "LP", "CRJ2": "LP",
    "RJ85": "LP", "RJ1H": "LP", "F70":  "LP",
    # No-Reactor +
    "AT72": "NR+", "AT76": "NR+", "DH8D": "NR+", "Q400": "NR+",
    # No-Reactor
    "AT43": "NR", "AT45": "NR", "DH8A": "NR", "DH8B": "NR", "DH8C": "NR",
    "SF34": "NR", "SF50": "NR",
    # No-Reactor lentos
    "BE20": "NR-", "BE99": "NR-", "BE9L": "NR-", "C208": "NR-",
    "PC12": "NR-", "DA42": "NR-", "DA62": "NR-",
}


def classify_aircraft(icao_type: str | None) -> str:
    """Devuelve la clase de motor para un tipo ICAO."""
    if not icao_type:
        return DEFAULT_ENGINE_CLASS
    return AIRCRAFT_CLASS.get(str(icao_type).strip().upper(), DEFAULT_ENGINE_CLASS)


# ---------------------------------------------------------------------------
# Familias de SIDs por pista (LEBL)
# Fuente: AIP España AD 2-LEBL SID charts.
# Misma familia => las trayectorias divergen poco en los primeros minutos.
# ---------------------------------------------------------------------------
SID_FAMILIES_24L: Dict[str, List[str]] = {
    "NORTH": ["VALMA", "GRAUS", "PIREN", "RUBOX"],
    "EAST":  ["MOPAS", "DALIN", "BARSA", "LOBAR"],
    "SOUTH": ["LOPRA", "SLL",   "VBA",   "MAKIL"],
}

SID_FAMILIES_06R: Dict[str, List[str]] = {
    "NORTH": ["VALMA", "GRAUS", "PIREN", "RUBOX"],
    "EAST":  ["MOPAS", "DALIN", "BARSA", "LOBAR"],
    "SOUTH": ["LOPRA", "SLL",   "VBA",   "MAKIL"],
}


def _sid_root(sid: str) -> str:
    """Recorta el sufijo numérico/letra de revisión del SID (e.g. VALMA1Q -> VALMA)."""
    s = str(sid).strip().upper()
    i = 0
    while i < len(s) and s[i].isalpha():
        i += 1
    return s[:i] if i else s


def get_sid_family(sid: str, runway: str) -> str | None:
    """Devuelve el nombre de la familia (NORTH/EAST/SOUTH) o None."""
    table = SID_FAMILIES_24L if "24" in runway else SID_FAMILIES_06R
    root = _sid_root(sid)
    for family, sids in table.items():
        if root in sids:
            return family
    return None


def same_sid_family(sid_a: str, sid_b: str, runway: str) -> bool:
    """¿Comparten ambos SIDs la misma familia para la pista dada?"""
    fa = get_sid_family(sid_a, runway)
    fb = get_sid_family(sid_b, runway)
    return fa is not None and fa == fb


# ---------------------------------------------------------------------------
# Constantes geográficas (decimal °)
# ---------------------------------------------------------------------------

def _dms(d: int, m: int, s: float) -> float:
    return d + m / 60.0 + s / 3600.0


# Cabeceras de pista (origen de los despegues)
THR_24L: Tuple[float, float] = (_dms(41, 17, 31.99), _dms(2, 6, 11.81))
THR_06R: Tuple[float, float] = (_dms(41, 16, 56.32), _dms(2, 4, 27.66))

# DVOR de Barcelona
DVOR_BCN: Tuple[float, float] = (_dms(41, 18, 25.6), _dms(2, 6, 28.1))

# Línea de la radial R-234 desde DVOR BCN hasta el extremo de costa
R234_LINE_ENDPOINTS: Tuple[Tuple[float, float], Tuple[float, float]] = (
    DVOR_BCN,
    (_dms(41, 16, 5.4), _dms(2, 2, 0.0)),
)

# Tangencia TMA (proyección estereográfica) — alineada con coordinate_transform.py
TMA_TANGENT_POINT: Tuple[float, float] = (_dms(41, 6, 56.560), _dms(1, 41, 33.010))
TMA_RADIUS_M: float = 6_368_942.808

# Filtro geográfico operativo
GEO_BBOX: Dict[str, float] = {
    "lat_min": 40.9,
    "lat_max": 41.7,
    "lon_min": 1.5,
    "lon_max": 2.6,
}

# Techo de filtrado (ft)
ALT_CEILING_FT: int = 6000

# Mínima radar (TWR)
RADAR_MIN_NM: float = 3.0
RADAR_MIN_VERT_FT: int = 1000

# Distancia mínima al THR para empezar a contar separación
START_FROM_THR_NM: float = 0.5


__all__ = [
    "WAKE_CATEGORIES", "WAKE_ALIASES", "normalize_wake",
    "WAKE_TWR", "WAKE_TMA", "get_wake_separation",
    "ENGINE_CLASSES", "LOA_TABLE", "get_loa_separation",
    "AIRCRAFT_CLASS", "DEFAULT_ENGINE_CLASS", "classify_aircraft",
    "SID_FAMILIES_24L", "SID_FAMILIES_06R",
    "get_sid_family", "same_sid_family",
    "THR_24L", "THR_06R", "DVOR_BCN", "R234_LINE_ENDPOINTS",
    "TMA_TANGENT_POINT", "TMA_RADIUS_M",
    "GEO_BBOX", "ALT_CEILING_FT",
    "RADAR_MIN_NM", "RADAR_MIN_VERT_FT", "START_FROM_THR_NM",
]
