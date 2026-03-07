"""Constantes para la integración NASA FIRMS Fires."""
from homeassistant.const import Platform

DOMAIN = "firms_nasa_fires"
PLATFORMS = [Platform.GEO_LOCATION]

# Versión
VERSION = "0.1.0"

# Configuración
CONF_API_KEY = "api_key"
CONF_RADIUS_KM = "radius_km"
CONF_UNITS = "units"
CONF_MIN_CONFIDENCE = "min_confidence"
CONF_DAYS = "days"
CONF_SOURCE = "source"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"

# Valores por defecto
DEFAULT_RADIUS_KM = 100
DEFAULT_UNITS = "km"
DEFAULT_MIN_CONFIDENCE = "l"
DEFAULT_DAYS = 1
DEFAULT_SOURCE = "VIIRS_SNPP_NRT"
DEFAULT_SCAN_INTERVAL = 15

# Límites
MIN_DAYS = 1
MAX_DAYS = 5
MIN_RADIUS = 10
MAX_RADIUS = 500
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 120

# Opciones para selectores
UNITS_OPTIONS = {
    "km": "Kilómetros",
    "mi": "Millas"
}

CONFIDENCE_OPTIONS = {
    "l": "Todas (baja, nominal, alta)",
    "n": "Nominal y alta (recomendado)",
    "h": "Solo alta"
}

SOURCE_OPTIONS = {
    "VIIRS_SNPP_NRT": "VIIRS SNPP (Tiempo Real)",
    "MODIS_NRT": "MODIS (Tiempo Real)",
    "VIIRS_NOAA20_NRT": "VIIRS NOAA-20 (Tiempo Real)"
}

CONFIDENCE_LEVELS = {
    "l": {"name": "Low", "value": 1, "icon": "mdi:smoke"},
    "n": {"name": "Nominal", "value": 2, "icon": "mdi:fire-circle"},
    "h": {"name": "High", "value": 3, "icon": "mdi:fire"}
}

KM_TO_MILES = 0.621371

FIRMS_API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{bbox}/{days}"

ATTRIBUTION = "Data provided by NASA FIRMS"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"
ATTR_BRIGHT_TI4 = "brightness_ti4"
ATTR_BRIGHT_TI5 = "brightness_ti5"
ATTR_SCAN = "scan"
ATTR_TRACK = "track"
ATTR_ACQ_DATE = "acquisition_date"
ATTR_ACQ_TIME = "acquisition_time"
ATTR_ACQ_LOCAL_TIME = "acquisition_local_time"
ATTR_ACQ_LOCAL_DATE = "acquisition_local_date"  # Nuevo
ATTR_SATELLITE = "satellite"
ATTR_INSTRUMENT = "instrument"
ATTR_CONFIDENCE = "confidence"
ATTR_CONFIDENCE_LEVEL = "confidence_level"
ATTR_CONFIDENCE_NAME = "confidence_name"
ATTR_VERSION = "version"
ATTR_FRP = "frp"
ATTR_DAYNIGHT = "daynight"
ATTR_DISTANCE = "distance"
ATTR_DISTANCE_KM = "distance_km"
ATTR_UNIT = "unit"