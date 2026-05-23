"""Proyección estereográfica conforme local para LEBL (Translib/Eurocontrol).

PDF P3 pág. 47:
- Punto de tangencia TMA: 41°06'56.560"N 1°41'33.010"E
- Radio de la esfera conforme: R = 6 368 942,808 m

Fórmula estereográfica conforme (origen en el punto de tangencia φ₀,λ₀):

    k  = 2R / (1 + sin φ₀ · sin φ + cos φ₀ · cos φ · cos(λ-λ₀))
    x  = k · cos φ · sin(λ-λ₀)
    y  = k · (cos φ₀ · sin φ - sin φ₀ · cos φ · cos(λ-λ₀))

Con X positivo hacia el Este geográfico y Y positivo hacia el Norte.
La inversa se obtiene con coordenadas polares en el plano:

    ρ  = √(x² + y²)
    c  = 2 · atan(ρ / 2R)
    φ  = asin(cos c · sin φ₀ + (y · sin c · cos φ₀) / ρ)
    λ  = λ₀ + atan2(x · sin c, ρ · cos φ₀ · cos c - y · sin φ₀ · sin c)
"""
import math
import numpy as np


# Tangente TMA y radio conforme (PDF pág. 47)
_TMA_LAT0_DEG = 41.0 + 6.0 / 60.0 + 56.560 / 3600.0    # 41°06'56.560"N
_TMA_LON0_DEG = 1.0 + 41.0 / 60.0 + 33.010 / 3600.0    # 001°41'33.010"E
_CONFORMAL_R_M = 6_368_942.808                         # m

# Alias retro-compatibles para código antiguo
LEBL_LAT0 = _TMA_LAT0_DEG
LEBL_LON0 = _TMA_LON0_DEG
EARTH_RADIUS_M = _CONFORMAL_R_M
NM_TO_M = 1852.0


def wgs84_to_stereographic(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Proyección estereográfica conforme centrada en la tangente TMA.

    Returns:
        (X, Y) en metros. X positivo → Este. Y positivo → Norte.
    """
    phi0 = math.radians(_TMA_LAT0_DEG)
    lam0 = math.radians(_TMA_LON0_DEG)
    phi = math.radians(lat_deg)
    lam = math.radians(lon_deg)
    dlam = lam - lam0

    cos_c = math.sin(phi0) * math.sin(phi) + math.cos(phi0) * math.cos(phi) * math.cos(dlam)
    k = 2.0 * _CONFORMAL_R_M / (1.0 + cos_c)
    x = k * math.cos(phi) * math.sin(dlam)
    y = k * (math.cos(phi0) * math.sin(phi) - math.sin(phi0) * math.cos(phi) * math.cos(dlam))
    return x, y


def stereographic_to_wgs84(x_m: float, y_m: float) -> tuple[float, float]:
    """Inversa de `wgs84_to_stereographic` (devuelve (lat°, lon°))."""
    phi0 = math.radians(_TMA_LAT0_DEG)
    lam0 = math.radians(_TMA_LON0_DEG)
    rho = math.hypot(x_m, y_m)
    if rho < 1e-9:
        return _TMA_LAT0_DEG, _TMA_LON0_DEG
    c = 2.0 * math.atan2(rho, 2.0 * _CONFORMAL_R_M)
    sin_c = math.sin(c)
    cos_c = math.cos(c)
    phi = math.asin(cos_c * math.sin(phi0) + (y_m * sin_c * math.cos(phi0)) / rho)
    lam = lam0 + math.atan2(
        x_m * sin_c,
        rho * math.cos(phi0) * cos_c - y_m * math.sin(phi0) * sin_c,
    )
    return math.degrees(phi), math.degrees(lam)


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine entre dos puntos WGS84 en NM."""
    R = _CONFORMAL_R_M / NM_TO_M
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def distance_m_stereo(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distancia euclidiana en el plano estereográfico (m)."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo verdadero (True Track) entre dos puntos WGS84 en grados [0,360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def add_stereo_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """Añade columnas `x_m`, `y_m` (estereográfica conforme, tangente TMA)
    al DataFrame de radar. Vectorizado en numpy."""
    phi0 = math.radians(_TMA_LAT0_DEG)
    lam0 = math.radians(_TMA_LON0_DEG)
    phi = np.radians(df["latitude"].to_numpy(dtype=float))
    lam = np.radians(df["longitude"].to_numpy(dtype=float))
    dlam = lam - lam0

    cos_c = np.sin(phi0) * np.sin(phi) + np.cos(phi0) * np.cos(phi) * np.cos(dlam)
    k = 2.0 * _CONFORMAL_R_M / (1.0 + cos_c)
    df = df.copy()
    df["x_m"] = k * np.cos(phi) * np.sin(dlam)
    df["y_m"] = k * (np.cos(phi0) * np.sin(phi) - np.sin(phi0) * np.cos(phi) * np.cos(dlam))
    return df


def dvor_bcn_radial(lat: float, lon: float) -> float:
    """Bearing FROM DVOR BCN hacia el punto dado (grados verdaderos)."""
    DVOR_LAT = 41.0 + 18.0 / 60.0 + 25.6 / 3600.0
    DVOR_LON = 2.0 + 6.0 / 60.0 + 28.1 / 3600.0
    return bearing_deg(DVOR_LAT, DVOR_LON, lat, lon)
