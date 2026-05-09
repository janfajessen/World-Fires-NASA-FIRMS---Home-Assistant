"""Plataforma binary_sensor para NASA FIRMS Fires — ¿hay incendios activos?"""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.core import callback

from .const import (
    DOMAIN,
    VERSION,
    ATTRIBUTION,
    CONF_UNITS,
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
    RISK_NONE,
    RISK_LOW,
    RISK_MEDIUM,
    RISK_HIGH,
    RISK_EXTREME,
    RISK_THRESHOLDS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Crear el binary_sensor de incendio activo para esta instancia."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([FirmsActiveFireBinarySensor(coordinator, entry)])
    return True


class FirmsActiveFireBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """
    True si hay al menos un incendio detectado en el área configurada.

    Perfecto para automatizaciones simples:
      - Encender una luz roja cuando is_on = True
      - Enviar notificación inmediata cuando pase de False a True
      - Combinado con risk_level para alertas escalonadas
    """

    _attr_should_poll = False
    _attr_device_class = BinarySensorDeviceClass.SMOKE

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_active_fire"

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
    def name(self) -> str:
        return "NASA FIRMS Active Fire"

    @property
    def is_on(self) -> bool:
        """True si hay al menos un incendio en el área."""
        return bool(self.coordinator.data)

    @property
    def icon(self) -> str:
        return "mdi:fire-alert" if self.is_on else "mdi:fire-off"

    def _get_risk_level(self, fires: list[dict]) -> str:
        """Calcula el nivel de riesgo para incluirlo como atributo."""
        if not fires:
            return RISK_NONE
        nearest_km = fires[0][ATTR_DISTANCE_KM]
        max_frp = max(f[ATTR_FRP] for f in fires)
        for level in (RISK_EXTREME, RISK_HIGH, RISK_MEDIUM):
            t = RISK_THRESHOLDS[level]
            if nearest_km <= t["max_dist_km"] or max_frp >= t["min_frp"]:
                return level
        return RISK_LOW

    @property
    def extra_state_attributes(self):
        fires = self.coordinator.data or []
        base = {
            "attribution":         ATTRIBUTION,
            "integration_version": VERSION,
            "total_fires":         len(fires),
        }
        if not fires:
            return {**base, "risk_level": RISK_NONE}

        nearest = fires[0]
        return {
            **base,
            "risk_level":          self._get_risk_level(fires),
            "nearest_distance":    round(nearest[ATTR_DISTANCE], 1),
            "nearest_distance_km": round(nearest[ATTR_DISTANCE_KM], 1),
            "unit":                nearest.get(ATTR_UNIT, "km"),
            "nearest_latitude":    nearest[ATTR_LATITUDE],
            "nearest_longitude":   nearest[ATTR_LONGITUDE],
            "nearest_confidence":  nearest.get(ATTR_CONFIDENCE_NAME, ""),
            "nearest_frp":         nearest.get(ATTR_FRP, 0),
            "nearest_source":      nearest.get(ATTR_SOURCE, ""),
            "nearest_daynight":    nearest.get(ATTR_DAYNIGHT, ""),
            "nearest_local_date":  nearest.get(ATTR_ACQ_LOCAL_DATE, ""),
            "nearest_local_time":  nearest.get(ATTR_ACQ_LOCAL_TIME, ""),
            "max_frp_mw":          round(max(f[ATTR_FRP] for f in fires), 1),
            "high_conf_fires":     sum(1 for f in fires if f.get("confidence_level") == "h"),
        }

    @callback
    def _handle_coordinator_update(self):
        self.async_write_ha_state()
        