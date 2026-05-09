"""Plataforma sensor para NASA FIRMS Fires — estadísticas por instancia."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.core import callback

from .const import (
    DOMAIN,
    VERSION,
    ATTRIBUTION,
    CONF_UNITS,
    SENSOR_TOTAL_FIRES,
    SENSOR_NEAREST_DISTANCE,
    SENSOR_MAX_FRP,
    SENSOR_NEAREST_NAME,
    SENSOR_FIRES_LAST_24H,
    SENSOR_FIRES_DAYTIME,
    SENSOR_FIRES_NIGHTTIME,
    SENSOR_AVERAGE_FRP,
    SENSOR_HIGH_CONF_COUNT,
    SENSOR_RISK_LEVEL,
    SENSOR_LAST_UPDATE,
    RISK_NONE,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_EXTREME,
    RISK_THRESHOLDS,
    ATTR_DISTANCE,
    ATTR_DISTANCE_KM,
    ATTR_FRP,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_CONFIDENCE_NAME,
    ATTR_SOURCE,
    ATTR_DAYNIGHT,
    ATTR_ACQ_LOCAL_DATE,
    ATTR_ACQ_LOCAL_TIME,
    ATTR_UNIT,
    ATTR_CONFIDENCE_LEVEL,
    ATTR_ACQ_DATE,
    ATTR_ACQ_TIME,
    ATTR_LOCATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Crear los 11 sensores de estadísticas para esta instancia."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    sensors = [
        FirmsTotalFiresSensor(coordinator, entry),
        FirmsNearestDistanceSensor(coordinator, entry),
        FirmsMaxFrpSensor(coordinator, entry),
        FirmsNearestNameSensor(coordinator, entry),
        # Nuevos v2.3
        FirmsFiresLast24hSensor(coordinator, entry),
        FirmsDaytimeFiresSensor(coordinator, entry),
        FirmsNighttimeFiresSensor(coordinator, entry),
        FirmsAverageFrpSensor(coordinator, entry),
        FirmsHighConfFiresSensor(coordinator, entry),
        FirmsRiskLevelSensor(coordinator, entry),
        FirmsLastUpdateSensor(coordinator, entry),
    ]
    async_add_entities(sensors)
    return True


# ---------------------------------------------------------------------------
# Base común
# ---------------------------------------------------------------------------

class FirmsBaseSensor(CoordinatorEntity, SensorEntity):
    """Clase base para todos los sensores de estadísticas."""

    _attr_should_poll = False

    def __init__(self, coordinator, entry, sensor_type: str):
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{sensor_type}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="NASA FIRMS",
            model="Fire Information for Resource Management System API",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://firms.modaps.eosdis.nasa.gov/api/",
        )

    @property
    def extra_state_attributes(self):
        return {
            "attribution": ATTRIBUTION,
            "integration_version": VERSION,
        }

    @callback
    def _handle_coordinator_update(self):
        self.async_write_ha_state()


# ---------------------------------------------------------------------------
# Sensor 1 — Total de incendios activos
# ---------------------------------------------------------------------------

class FirmsTotalFiresSensor(FirmsBaseSensor):
    """Número total de incendios detectados en el área configurada."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_TOTAL_FIRES)
        self._attr_icon = "mdi:fire-alert"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Total Fires"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        return len(fires)

    @property
    def native_unit_of_measurement(self):
        return "fires"

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = super().extra_state_attributes
        # Desglose por nivel de confianza
        low     = sum(1 for f in fires if f.get("confidence_level") == "l")
        nominal = sum(1 for f in fires if f.get("confidence_level") == "n")
        high    = sum(1 for f in fires if f.get("confidence_level") == "h")
        # Desglose por fuente
        sources: dict[str, int] = {}
        for f in fires:
            src = f.get(ATTR_SOURCE, "unknown")
            sources[src] = sources.get(src, 0) + 1
        return {
            **base,
            "fires_low_confidence":     low,
            "fires_nominal_confidence": nominal,
            "fires_high_confidence":    high,
            "fires_by_source":          sources,
        }


# ---------------------------------------------------------------------------
# Sensor 2 — Distancia al incendio más cercano
# ---------------------------------------------------------------------------

class FirmsNearestDistanceSensor(FirmsBaseSensor):
    """Distancia al incendio más cercano al centro configurado."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_NEAREST_DISTANCE)
        self._attr_icon = "mdi:map-marker-distance"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Nearest Fire Distance"

    @property
    def native_unit_of_measurement(self) -> str:
        # Respeta la unidad elegida por el usuario
        return self._entry.options.get(CONF_UNITS, "km")

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        if not fires:
            return None
        nearest = fires[0]   # ya están ordenados por distancia
        return round(nearest[ATTR_DISTANCE], 1)

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = super().extra_state_attributes
        if not fires:
            return base
        nearest = fires[0]
        return {
            **base,
            "latitude":       nearest[ATTR_LATITUDE],
            "longitude":      nearest[ATTR_LONGITUDE],
            "confidence":     nearest.get(ATTR_CONFIDENCE_NAME, ""),
            "source":         nearest.get(ATTR_SOURCE, ""),
            "frp":            nearest.get(ATTR_FRP, 0),
            "daynight":       nearest.get(ATTR_DAYNIGHT, ""),
            "local_date":     nearest.get(ATTR_ACQ_LOCAL_DATE, ""),
            "local_time":     nearest.get(ATTR_ACQ_LOCAL_TIME, ""),
            "distance_km":    round(nearest[ATTR_DISTANCE_KM], 1),
            "location":       nearest.get(ATTR_LOCATION_NAME, ""),
        }


# ---------------------------------------------------------------------------
# Sensor 3 — Máximo FRP (Fire Radiative Power)
# ---------------------------------------------------------------------------

class FirmsMaxFrpSensor(FirmsBaseSensor):
    """
    FRP más alto detectado en el área — mide la energía radiativa del fuego en MW.
    Valores altos indican incendios más intensos o de mayor tamaño.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_MAX_FRP)
        self._attr_icon = "mdi:fire"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Max FRP"

    @property
    def native_unit_of_measurement(self) -> str:
        return "MW"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        if not fires:
            return None
        return round(max(f[ATTR_FRP] for f in fires), 1)

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = super().extra_state_attributes
        if not fires:
            return base
        hottest = max(fires, key=lambda f: f[ATTR_FRP])
        return {
            **base,
            "latitude":    hottest[ATTR_LATITUDE],
            "longitude":   hottest[ATTR_LONGITUDE],
            "confidence":  hottest.get(ATTR_CONFIDENCE_NAME, ""),
            "source":      hottest.get(ATTR_SOURCE, ""),
            "distance_km": round(hottest[ATTR_DISTANCE_KM], 1),
            "distance":    round(hottest[ATTR_DISTANCE], 1),
            "unit":        hottest.get(ATTR_UNIT, "km"),
            "daynight":    hottest.get(ATTR_DAYNIGHT, ""),
            "local_date":  hottest.get(ATTR_ACQ_LOCAL_DATE, ""),
            "local_time":  hottest.get(ATTR_ACQ_LOCAL_TIME, ""),
            "location":    hottest.get(ATTR_LOCATION_NAME, ""),
        }


# ---------------------------------------------------------------------------
# Sensor 4 — Nombre del incendio más cercano
# ---------------------------------------------------------------------------

class FirmsNearestNameSensor(FirmsBaseSensor):
    """
    Nombre de la entidad del incendio más cercano.
    Útil para referenciar la entidad geo_location en automatizaciones.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_NEAREST_NAME)
        self._attr_icon = "mdi:map-marker-alert"

    @property
    def name(self) -> str:
        return "NASA FIRMS Nearest Fire"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        if not fires:
            return "No fires detected"
        nearest = fires[0]
        location = nearest.get(ATTR_LOCATION_NAME, "")
        lat = round(nearest[ATTR_LATITUDE],  2)
        lon = round(nearest[ATTR_LONGITUDE], 2)
        confidence = nearest.get(ATTR_CONFIDENCE_NAME, "")
        suffix = f" — {location}" if location else ""
        return f"{confidence} conf Fire NASA FIRMS ({lat}, {lon}){suffix}"

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = super().extra_state_attributes
        if not fires:
            return {**base, "fires_detected": False}
        nearest = fires[0]
        return {
            **base,
            "fires_detected": True,
            "latitude":       nearest[ATTR_LATITUDE],
            "longitude":      nearest[ATTR_LONGITUDE],
            "distance":       round(nearest[ATTR_DISTANCE], 1),
            "distance_km":    round(nearest[ATTR_DISTANCE_KM], 1),
            "unit":           nearest.get(ATTR_UNIT, "km"),
            "confidence":     nearest.get(ATTR_CONFIDENCE_NAME, ""),
            "frp":            nearest.get(ATTR_FRP, 0),
            "source":         nearest.get(ATTR_SOURCE, ""),
            "daynight":       nearest.get(ATTR_DAYNIGHT, ""),
            "local_date":     nearest.get(ATTR_ACQ_LOCAL_DATE, ""),
            "local_time":     nearest.get(ATTR_ACQ_LOCAL_TIME, ""),
            "location":       nearest.get(ATTR_LOCATION_NAME, ""),
        }


# ---------------------------------------------------------------------------
# Sensor 5 — Incendios nuevos en las últimas 24h
# ---------------------------------------------------------------------------

class FirmsFiresLast24hSensor(FirmsBaseSensor):
    """
    Incendios con fecha de adquisición en las últimas 24 horas.
    Útil para ver actividad reciente sin contar datos históricos de días atrás.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_FIRES_LAST_24H)
        self._attr_icon = "mdi:fire-hydrant-alert"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Fires Last 24h"

    @property
    def native_unit_of_measurement(self):
        return "fires"

    @property
    def native_value(self):
        from datetime import datetime, timezone, timedelta
        fires = self.coordinator.data or []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        count = 0
        for f in fires:
            try:
                acq_date = f.get(ATTR_ACQ_DATE, "")
                acq_time = f.get(ATTR_ACQ_TIME, "").zfill(4)
                dt = datetime.strptime(
                    f"{acq_date} {acq_time[:2]}:{acq_time[2:]}:00", "%Y-%m-%d %H:%M:%S"
                ).replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    count += 1
            except Exception:
                continue
        return count


# ---------------------------------------------------------------------------
# Sensor 6 — Incendios diurnos
# ---------------------------------------------------------------------------

class FirmsDaytimeFiresSensor(FirmsBaseSensor):
    """Incendios detectados durante el día (pase diurno del satélite)."""

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_FIRES_DAYTIME)
        self._attr_icon = "mdi:weather-sunny-alert"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Daytime Fires"

    @property
    def native_unit_of_measurement(self):
        return "fires"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        return sum(1 for f in fires if f.get(ATTR_DAYNIGHT, "") == "D")


# ---------------------------------------------------------------------------
# Sensor 7 — Incendios nocturnos
# ---------------------------------------------------------------------------

class FirmsNighttimeFiresSensor(FirmsBaseSensor):
    """
    Incendios detectados durante la noche (pase nocturno del satélite).
    Las detecciones nocturnas de VIIRS son especialmente precisas porque
    el sensor TI4 no tiene interferencia solar — valores más fiables.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_FIRES_NIGHTTIME)
        self._attr_icon = "mdi:weather-night"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Nighttime Fires"

    @property
    def native_unit_of_measurement(self):
        return "fires"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        return sum(1 for f in fires if f.get(ATTR_DAYNIGHT, "") == "N")


# ---------------------------------------------------------------------------
# Sensor 8 — FRP medio
# ---------------------------------------------------------------------------

class FirmsAverageFrpSensor(FirmsBaseSensor):
    """
    FRP medio de todos los incendios detectados en el área.
    Indica la intensidad media general — útil para detectar tendencias
    (un valor subiendo puede indicar un incendio que se extiende).
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_AVERAGE_FRP)
        self._attr_icon = "mdi:fire-circle"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS Average FRP"

    @property
    def native_unit_of_measurement(self):
        return "MW"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        if not fires:
            return None
        frp_values = [f[ATTR_FRP] for f in fires if f[ATTR_FRP] > 0]
        if not frp_values:
            return None
        return round(sum(frp_values) / len(frp_values), 1)


# ---------------------------------------------------------------------------
# Sensor 9 — Incendios de alta confianza
# ---------------------------------------------------------------------------

class FirmsHighConfFiresSensor(FirmsBaseSensor):
    """
    Número de incendios con nivel de confianza ALTO.
    Útil para automatizaciones críticas que solo deben dispararse
    ante detecciones muy fiables, ignorando posibles falsos positivos.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_HIGH_CONF_COUNT)
        self._attr_icon = "mdi:fire"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def name(self) -> str:
        return "NASA FIRMS High Confidence Fires"

    @property
    def native_unit_of_measurement(self):
        return "fires"

    @property
    def native_value(self):
        fires = self.coordinator.data or []
        return sum(1 for f in fires if f.get(ATTR_CONFIDENCE_LEVEL) == "h")

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        high = [f for f in fires if f.get(ATTR_CONFIDENCE_LEVEL) == "h"]
        base = super().extra_state_attributes
        if not high:
            return base
        nearest = min(high, key=lambda f: f[ATTR_DISTANCE_KM])
        return {
            **base,
            "nearest_high_conf_distance_km": round(nearest[ATTR_DISTANCE_KM], 1),
            "nearest_high_conf_frp":         nearest[ATTR_FRP],
            "nearest_high_conf_source":      nearest.get(ATTR_SOURCE, ""),
        }


# ---------------------------------------------------------------------------
# Sensor 10 — Nivel de riesgo calculado
# ---------------------------------------------------------------------------

class FirmsRiskLevelSensor(FirmsBaseSensor):
    """
    Nivel de riesgo calculado combinando distancia, FRP y número de incendios.

    Niveles:
      none    → Sin incendios detectados en el área
      low     → Incendios detectados pero lejos y/o de baja intensidad
      medium  → Incendio a < 100 km O FRP > 10 MW
      high    → Incendio a < 50 km  O FRP > 100 MW
      extreme → Incendio a < 20 km  O FRP > 500 MW

    Útil para automatizaciones simples sin necesidad de templates complejos:
    disparar notificación cuando risk_level pase a 'high' o 'extreme'.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_RISK_LEVEL)
        self._attr_icon = "mdi:shield-fire"

    @property
    def name(self) -> str:
        return "NASA FIRMS Fire Risk Level"

    @property
    def native_value(self) -> str:
        fires = self.coordinator.data or []
        if not fires:
            return RISK_NONE

        nearest_km = fires[0][ATTR_DISTANCE_KM]   # ya ordenados por distancia
        max_frp = max(f[ATTR_FRP] for f in fires)

        for level in (RISK_EXTREME, RISK_HIGH, RISK_MEDIUM):
            thresholds = RISK_THRESHOLDS[level]
            if nearest_km <= thresholds["max_dist_km"] or max_frp >= thresholds["min_frp"]:
                return level

        return RISK_LOW

    @property
    def icon(self) -> str:
        icons = {
            RISK_NONE:    "mdi:shield-check",
            RISK_LOW:     "mdi:shield-outline",
            RISK_MEDIUM:  "mdi:shield-alert-outline",
            RISK_HIGH:    "mdi:shield-alert",
            RISK_EXTREME: "mdi:shield-fire",
        }
        return icons.get(self.native_value, "mdi:shield-fire")

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = super().extra_state_attributes
        if not fires:
            return {**base, "total_fires": 0}
        return {
            **base,
            "total_fires":        len(fires),
            "nearest_fire_km":    round(fires[0][ATTR_DISTANCE_KM], 1),
            "max_frp_mw":         round(max(f[ATTR_FRP] for f in fires), 1),
            "high_conf_fires":    sum(1 for f in fires if f.get(ATTR_CONFIDENCE_LEVEL) == "h"),
            "risk_nearest_km_threshold":  RISK_THRESHOLDS.get(self.native_value, {}).get("max_dist_km", "—"),
            "risk_frp_threshold_mw":      RISK_THRESHOLDS.get(self.native_value, {}).get("min_frp", "—"),
        }


# ---------------------------------------------------------------------------
# Sensor 11 — Fecha y hora del último update del coordinator
# ---------------------------------------------------------------------------

class FirmsLastUpdateSensor(FirmsBaseSensor):
    """
    Fecha y hora local del último update completado correctamente.
    Útil para verificar que el scan interval funciona y los datos son frescos.
    Estado: timestamp ISO 8601 local. Si nunca ha actualizado: 'Never'.
    """

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, SENSOR_LAST_UPDATE)
        self._attr_icon = "mdi:clock-check-outline"

    @property
    def name(self) -> str:
        return "NASA FIRMS Last Update"

    @property
    def native_value(self):
        val = getattr(self.coordinator, "last_firms_update", None)
        return val if val is not None else "Never"

    @property
    def extra_state_attributes(self):
        base = super().extra_state_attributes
        coordinator = self.coordinator
        return {
            **base,
            "last_update_success": coordinator.last_update_success,
            "update_interval_min": int(coordinator.update_interval.total_seconds() // 60)
            if coordinator.update_interval else None,
        }
