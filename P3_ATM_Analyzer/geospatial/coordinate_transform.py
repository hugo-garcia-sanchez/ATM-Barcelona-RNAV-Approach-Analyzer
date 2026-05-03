"""Transformacion de coordenadas WGS84 a estereografica local para Barcelona LEBL."""
import math
import numpy as np

# Centro de proyeccion: umbral RWY 24L de LEBL
LEBL_LAT0 = 41.2865   # grados
LEBL_LON0 = 2.0759    # grados
EARTH_RADIUS_M = 6_371_000.0  # radio medio Tierra en metros
NM_TO_M = 1852.0


def wgs84_to_stereographic(lat_deg: float, lon_deg: float) -> tuple[float, float]:
    """Proyeccion estereografica local centrada en LEBL.

    Usa proyeccion azimutal equidistante (azimuthal equidistant) que
    equivale a la estereografica para analisis local de corta distancia.

    Returns:
        (X, Y) en metros. X positivo -> Este. Y positivo -> Norte.
    """
    lat0 = math.radians(LEBL_LAT0)
    lon0 = math.radians(LEBL_LON0)
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)

    dlat = lat - lat0
    dlon = lon - lon0

    # Proyeccion plana (valida para distancias < 500 km)
    x = EARTH_RADIUS_M * dlon * math.cos(lat0)
    y = EARTH_RADIUS_M * dlat

    return x, y


def stereographic_to_wgs84(x_m: float, y_m: float) -> tuple[float, float]:
    """Proyeccion inversa: (X,Y) metros -> (lat, lon) grados."""
    lat0 = math.radians(LEBL_LAT0)
    lon0 = math.radians(LEBL_LON0)

    lat = math.radians(LEBL_LAT0) + y_m / EARTH_RADIUS_M
    lon = lon0 + (x_m / EARTH_RADIUS_M) / math.cos(lat0)

    return math.degrees(lat), math.degrees(lon)


def distance_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia haversine entre dos puntos WGS84 en millas nauticas."""
    R = EARTH_RADIUS_M / NM_TO_M
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def distance_m_stereo(x1: float, y1: float, x2: float, y2: float) -> float:
    """Distancia euclidiana en proyeccion estereografica (metros)."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Rumbo verdadero (True Track) desde punto 1 a punto 2 en grados [0,360)."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlambda = math.radians(lon2 - lon1)
    x = math.sin(dlambda) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlambda)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def add_stereo_columns(df: "pd.DataFrame") -> "pd.DataFrame":
    """Anade columnas x_m, y_m a un DataFrame con columnas latitude, longitude.

    Vectorised with numpy: avoids row-wise Python apply for large radar datasets.
    """
    lat0 = math.radians(LEBL_LAT0)
    lon0 = math.radians(LEBL_LON0)
    lat = np.radians(df["latitude"].to_numpy(dtype=float))
    lon = np.radians(df["longitude"].to_numpy(dtype=float))
    df = df.copy()
    df["x_m"] = EARTH_RADIUS_M * (lon - lon0) * math.cos(lat0)
    df["y_m"] = EARTH_RADIUS_M * (lat - lat0)
    return df


def dvor_bcn_radial(lat: float, lon: float) -> float:
    """Calcula el radial del DVOR BCN hacia el punto dado (grados magneticos aprox. verdaderos).

    DVOR BCN: 41.307111 N, 2.107806 E
    El radial es el FROM bearing: desde DVOR hacia el punto.
    """
    DVOR_LAT = 41.307111
    DVOR_LON = 2.107806
    return bearing_deg(DVOR_LAT, DVOR_LON, lat, lon)
