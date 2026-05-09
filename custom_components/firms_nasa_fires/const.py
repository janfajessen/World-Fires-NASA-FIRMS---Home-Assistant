"""Constantes para la integración NASA FIRMS Fires."""
from homeassistant.const import Platform

DOMAIN = "firms_nasa_fires"
PLATFORMS = [Platform.GEO_LOCATION, Platform.SENSOR, Platform.BINARY_SENSOR]

VERSION = "2.3.0"

# Configuración
CONF_API_KEY      = "api_key"
CONF_RADIUS_KM    = "radius_km"
CONF_UNITS        = "units"
CONF_MIN_CONFIDENCE = "min_confidence"
CONF_DAYS         = "days"
CONF_SOURCE       = "source"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_LATITUDE     = "latitude"
CONF_LONGITUDE    = "longitude"
CONF_DAYNIGHT     = "daynight"       # Nuevo v2.1.1: filtro día/noche
CONF_DATE         = "date"           # Nuevo v2.1.1: fecha histórica opcional

# Valores por defecto
DEFAULT_RADIUS_KM    = 100
DEFAULT_UNITS        = "km"
DEFAULT_MIN_CONFIDENCE = "l"
DEFAULT_DAYS         = 1
DEFAULT_SOURCE       = ["VIIRS_SNPP_NRT"]
DEFAULT_SCAN_INTERVAL = 15
DEFAULT_DAYNIGHT     = "all"         # all | D | N
DEFAULT_DATE         = ""            # Vacío = usar días hacia atrás (comportamiento normal)

# Límites
MIN_DAYS         = 1
MAX_DAYS         = 5
MIN_RADIUS       = 10
MAX_RADIUS       = 500
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 120

# Máximo de instancias simultáneas
MAX_INSTANCES = 10

# Deduplicación entre satélites
DEDUP_RADIUS_KM      = 0.5    # km — mismo incendio detectado por dos satélites
DEDUP_TIME_WINDOW_MIN = 180   # minutos — ventana temporal de dedup

# ---------------------------------------------------------------------------
# Fuentes de satélite
# ---------------------------------------------------------------------------
# VIIRS:   resolución 375 m, ideal para incendios pequeños/medianos
# MODIS:   resolución 1 km, ~4 pases/día, más antiguo
# Landsat: resolución 30 m (!), pero menos frecuencia de paso (~16 días/ciclo)
SOURCE_OPTIONS = {
    "VIIRS_SNPP_NRT":   "VIIRS SNPP (Real-time)",
    "MODIS_NRT":        "MODIS (Real-time)",
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20 (Real-time)",
    "VIIRS_NOAA21_NRT": "VIIRS NOAA-21 (Real-time)",
    "LANDSAT_NRT":      "Landsat 8/9 (Real-time)",    # Nuevo v2.1.1
}

# Fuentes que usan campos MODIS/Landsat en el CSV (brightness / bright_t31)
MODIS_SOURCES = {"MODIS_NRT", "LANDSAT_NRT"}
# Fuentes que usan campos VIIRS (bright_ti4 / bright_ti5)
VIIRS_SOURCES = {"VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"}

# ---------------------------------------------------------------------------
# Opciones de filtro día/noche
# ---------------------------------------------------------------------------
# D = detección diurna (luz solar → más interferencia solar pero más pases)
# N = detección nocturna (sin sol → VIIRS más sensible, menos falsos positivos
#     industriales como hornos, gas flaring, luces de ciudad)
# all = sin filtro (recomendado para incendios forestales reales)
DAYNIGHT_OPTIONS = {
    "all": "All (day and night)",
    "D":   "Day only",
    "N":   "Night only",
}

UNITS_OPTIONS = {
    "km": "Kilómetros",
    "mi": "Millas",
}

CONFIDENCE_OPTIONS = {
    "l": "Todas (baja, nominal, alta)",
    "n": "Nominal y alta (recomendado)",
    "h": "Solo alta",
}

CONFIDENCE_LEVELS = {
    "l": {"name": "Low",     "value": 1, "icon": "mdi:smoke"},
    "n": {"name": "Nominal", "value": 2, "icon": "mdi:fire-circle"},
    "h": {"name": "High",    "value": 3, "icon": "mdi:fire"},
}

KM_TO_MILES = 0.621371

# URL base — si se añade fecha: .../days/YYYY-MM-DD
FIRMS_API_URL = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    "/{api_key}/{source}/{bbox}/{days}"
)
FIRMS_API_URL_DATE = (
    "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    "/{api_key}/{source}/{bbox}/1/{date}"
)

ATTRIBUTION = "Data provided by NASA FIRMS"

# ---------------------------------------------------------------------------
# Atributos de entidades geo_location
# ---------------------------------------------------------------------------
ATTR_LATITUDE         = "latitude"
ATTR_LONGITUDE        = "longitude"
ATTR_SCAN             = "scan"
ATTR_TRACK            = "track"
ATTR_ACQ_DATE         = "acquisition_date"
ATTR_ACQ_TIME         = "acquisition_time"
ATTR_ACQ_LOCAL_TIME   = "acquisition_local_time"
ATTR_ACQ_LOCAL_DATE   = "acquisition_local_date"
ATTR_SATELLITE        = "satellite"
ATTR_INSTRUMENT       = "instrument"
ATTR_CONFIDENCE       = "confidence"
ATTR_CONFIDENCE_LEVEL = "confidence_level"
ATTR_CONFIDENCE_NAME  = "confidence_name"
ATTR_VERSION          = "version"
ATTR_FRP              = "frp"
ATTR_DAYNIGHT         = "daynight"
ATTR_DISTANCE         = "distance"
ATTR_DISTANCE_KM      = "distance_km"
ATTR_UNIT             = "unit"
ATTR_SOURCE           = "source"
ATTR_LOCATION_NAME    = "location"      # Nombre del lugar obtenido por geocodificación inversa

# VIIRS
ATTR_BRIGHT_TI4 = "brightness_ti4"
ATTR_BRIGHT_TI5 = "brightness_ti5"

# MODIS / Landsat
ATTR_BRIGHTNESS = "brightness"
ATTR_BRIGHT_T31 = "brightness_t31"


# Filtro FRP mínimo (v2.2)
# Fire Radiative Power: energía que el satélite mide que el fuego emite en MW.
# < 10 MW  → fuego pequeño, quema controlada o inicio de incendio
# 10-100 MW → incendio forestal activo moderado
# 100-1000 MW → incendio grande y muy activo
# > 1000 MW → incendio extremo (grandes incendios de California, Australia...)
# Útil para filtrar falsos positivos industriales (hornos, gas flaring)
# que suelen dar < 15-30 MW. 0 = sin filtro (muestra todo).
CONF_MIN_FRP      = "min_frp"
DEFAULT_MIN_FRP   = 0      # MW — 0 = sin filtro, comportamiento idéntico a v2.1.x
MIN_FRP_VALUE     = 0      # MW
MAX_FRP_VALUE     = 500    # MW
# ---------------------------------------------------------------------------
# Sensores de estadísticas (nuevos v2.1.1)
# ---------------------------------------------------------------------------
SENSOR_TOTAL_FIRES       = "total_fires"
SENSOR_NEAREST_DISTANCE  = "nearest_fire_distance"
SENSOR_MAX_FRP           = "max_frp"
SENSOR_NEAREST_NAME      = "nearest_fire_name"

# ---------------------------------------------------------------------------
# Eventos del bus de HA (v2.3)
# ---------------------------------------------------------------------------
# Se dispara en hass.bus cuando aparece un incendio nuevo no visto antes
EVENT_NEW_FIRE = f"{DOMAIN}_new_fire"

# ---------------------------------------------------------------------------
# Niveles de riesgo calculado (v2.3)
# ---------------------------------------------------------------------------
RISK_NONE    = "none"
RISK_LOW     = "low"
RISK_MEDIUM  = "medium"
RISK_HIGH    = "high"
RISK_EXTREME = "extreme"

# Lógica de riesgo (umbrales configurables aquí):
#   EXTREME: incendio a < 20 km  O  FRP máximo > 500 MW
#   HIGH:    incendio a < 50 km  O  FRP máximo > 100 MW
#   MEDIUM:  incendio a < 100 km O  FRP máximo > 10 MW
#   LOW:     hay incendios pero fuera de los umbrales anteriores
#   NONE:    sin incendios detectados
RISK_THRESHOLDS = {
    RISK_EXTREME: {"max_dist_km": 20,  "min_frp": 500},
    RISK_HIGH:    {"max_dist_km": 50,  "min_frp": 100},
    RISK_MEDIUM:  {"max_dist_km": 100, "min_frp": 10},
}

# ---------------------------------------------------------------------------
# Sensores de estadísticas adicionales (v2.3)
# ---------------------------------------------------------------------------
SENSOR_FIRES_LAST_24H      = "fires_last_24h"
SENSOR_FIRES_DAYTIME       = "fires_daytime"
SENSOR_FIRES_NIGHTTIME     = "fires_nighttime"
SENSOR_AVERAGE_FRP         = "average_frp"
SENSOR_HIGH_CONF_COUNT     = "high_confidence_fires"
SENSOR_RISK_LEVEL          = "fire_risk_level"
SENSOR_LAST_UPDATE         = "last_update"
