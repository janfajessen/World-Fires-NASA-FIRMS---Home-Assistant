"""Plataforma geo_location para NASA FIRMS Fires."""
import logging
from datetime import timedelta, datetime
import csv
from io import StringIO
import math

import aiohttp
import async_timeout
from haversine import haversine, Unit
from zoneinfo import ZoneInfo

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.core import callback

from .const import (
    DOMAIN,
    VERSION,
    CONF_RADIUS_KM,
    CONF_UNITS,
    CONF_MIN_CONFIDENCE,
    CONF_DAYS,
    CONF_SOURCE,
    CONF_SCAN_INTERVAL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEFAULT_SCAN_INTERVAL,
    CONFIDENCE_LEVELS,
    KM_TO_MILES,
    FIRMS_API_URL,
    ATTRIBUTION,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_BRIGHT_TI4,
    ATTR_BRIGHT_TI5,
    ATTR_SCAN,
    ATTR_TRACK,
    ATTR_ACQ_DATE,
    ATTR_ACQ_TIME,
    ATTR_ACQ_LOCAL_TIME,
    ATTR_ACQ_LOCAL_DATE,
    ATTR_SATELLITE,
    ATTR_INSTRUMENT,
    ATTR_CONFIDENCE,
    ATTR_CONFIDENCE_LEVEL,
    ATTR_CONFIDENCE_NAME,
    ATTR_VERSION,
    ATTR_FRP,
    ATTR_DAYNIGHT,
    ATTR_DISTANCE,
    ATTR_DISTANCE_KM,
    ATTR_UNIT,
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = FirmsDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    async def _add_new_entities():
        entity_registry = er.async_get(hass)
        new_entities = []
        for fire_data in coordinator.data or []:
            unique_id = f"{fire_data[ATTR_CONFIDENCE_LEVEL]}_conf_fire_nasa_firms_{fire_data[ATTR_LATITUDE]}_{fire_data[ATTR_LONGITUDE]}_{fire_data[ATTR_ACQ_DATE]}_{fire_data[ATTR_ACQ_TIME]}"
            if not entity_registry.async_get_entity_id("geo_location", DOMAIN, unique_id):
                new_entities.append(FirmsGeolocation(fire_data, coordinator, entry))
        if new_entities:
            async_add_entities(new_entities)

    await _add_new_entities()
    entry.async_on_unload(coordinator.async_add_listener(lambda: hass.async_create_task(_add_new_entities())))

    return True

def get_confidence_level(confidence_value):
    if confidence_value is None:
        return "l"
    
    conf_str = str(confidence_value).lower().strip()
    
    if conf_str in ["l", "n", "h"]:
        return conf_str
    
    try:
        conf_num = int(float(conf_str))
        if conf_num <= 10:
            return "l"
        elif conf_num <= 20:
            return "n"
        else:
            return "h"
    except:
        return "l"

class FirmsDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.entry = entry
        self.hass = hass

    async def _async_update_data(self):
        api_key = self.entry.data[CONF_API_KEY]
        radius = self.entry.options[CONF_RADIUS_KM]
        units = self.entry.options[CONF_UNITS]
        min_confidence = self.entry.options[CONF_MIN_CONFIDENCE]
        source = self.entry.options[CONF_SOURCE]
        days = self.entry.options[CONF_DAYS]
        
        home_lat = self.entry.data[CONF_LATITUDE]
        home_lon = self.entry.data[CONF_LONGITUDE]
        
        lat_offset = radius / 111.0
        lon_offset = radius / (111.0 * abs(math.cos(math.radians(home_lat))) + 0.01)
        
        min_lat = home_lat - lat_offset
        max_lat = home_lat + lat_offset
        min_lon = home_lon - lon_offset
        max_lon = home_lon + lon_offset
        
        bbox = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        url = FIRMS_API_URL.format(api_key=api_key, source=source, bbox=bbox, days=days)
        
        _LOGGER.debug(f"Fetching FIRMS data with URL: {url} (home coords: {home_lat}, {home_lon}, radius: {radius} km)")
        
        try:
            async with async_timeout.timeout(30):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            _LOGGER.error(f"FIRMS API error {response.status}: {error_text}")
                            raise UpdateFailed(f"Error: {response.status} - {error_text}")
                        
                        text_data = await response.text()
                        fires = []
                        csv_reader = csv.DictReader(StringIO(text_data))
                        confidence_values = {"l": 1, "n": 2, "h": 3}
                        min_value = confidence_values.get(min_confidence, 1)
                        
                        for row in csv_reader:
                            try:
                                fire_lat = float(row["latitude"])
                                fire_lon = float(row["longitude"])
                                
                                distance_km = haversine(
                                    (home_lat, home_lon),
                                    (fire_lat, fire_lon),
                                    unit=Unit.KILOMETERS
                                )
                                
                                if distance_km <= radius:
                                    confidence_level = get_confidence_level(row.get("confidence"))
                                    current_value = confidence_values.get(confidence_level, 1)
                                    
                                    if current_value >= min_value:
                                        distance = distance_km
                                        if units == "mi":
                                            distance = distance_km * KM_TO_MILES
                                        
                                        acq_date = row.get("acq_date", "")
                                        acq_time = row.get("acq_time", "")
                                        
                                        local_date_str = ""
                                        local_time_str = ""
                                        
                                        if acq_date and acq_time:
                                            acq_time_padded = acq_time.zfill(4)
                                            acq_hour = acq_time_padded[:2]
                                            acq_min = acq_time_padded[2:]
                                            acq_datetime_str = f"{acq_date} {acq_hour}:{acq_min}:00"
                                            
                                            try:
                                                acq_utc = datetime.strptime(acq_datetime_str, "%Y-%m-%d %H:%M:%S")
                                                acq_utc = acq_utc.replace(tzinfo=ZoneInfo("UTC"))
                                                local_tz = ZoneInfo(self.hass.config.time_zone)
                                                acq_local = acq_utc.astimezone(local_tz)
                                                local_date_str = acq_local.strftime("%d-%m-%Y")
                                                local_time_str = acq_local.strftime("%H:%M")
                                            except ValueError as e:
                                                _LOGGER.debug(f"Error parsing datetime: {e}")
                                        
                                        fire_data = {
                                            ATTR_LATITUDE: fire_lat,
                                            ATTR_LONGITUDE: fire_lon,
                                            ATTR_BRIGHT_TI4: float(row.get("bright_ti4", 0)),
                                            ATTR_BRIGHT_TI5: float(row.get("bright_ti5", 0)) if row.get("bright_ti5") else 0,
                                            ATTR_SCAN: float(row.get("scan", 0)),
                                            ATTR_TRACK: float(row.get("track", 0)),
                                            ATTR_ACQ_DATE: acq_date,
                                            ATTR_ACQ_TIME: acq_time,
                                            ATTR_ACQ_LOCAL_TIME: local_time_str,
                                            ATTR_ACQ_LOCAL_DATE: local_date_str,
                                            ATTR_SATELLITE: row.get("satellite", ""),
                                            ATTR_INSTRUMENT: row.get("instrument", ""),
                                            ATTR_CONFIDENCE: row.get("confidence", ""),
                                            ATTR_CONFIDENCE_LEVEL: confidence_level,
                                            ATTR_CONFIDENCE_NAME: CONFIDENCE_LEVELS[confidence_level]["name"],
                                            ATTR_VERSION: row.get("version", ""),
                                            ATTR_FRP: float(row.get("frp", 0)),
                                            ATTR_DAYNIGHT: row.get("daynight", ""),
                                            ATTR_DISTANCE_KM: distance_km,
                                            ATTR_DISTANCE: distance,
                                            ATTR_UNIT: units,
                                        }
                                        fires.append(fire_data)
                            except Exception as e:
                                _LOGGER.debug(f"Error processing row: {e}")
                                continue
                        
                        fires.sort(key=lambda x: x[ATTR_DISTANCE])
                        return fires
        except Exception as err:
            raise UpdateFailed(f"Error: {err}")

class FirmsGeolocation(CoordinatorEntity, GeolocationEvent):
    _attr_should_poll = False

    def __init__(self, fire_data, coordinator, entry):
        super().__init__(coordinator)
        self._fire_data = fire_data
        self._entry = entry
        self._unique_id = f"{fire_data[ATTR_CONFIDENCE_LEVEL]}_conf_fire_nasa_firms_{fire_data[ATTR_LATITUDE]}_{fire_data[ATTR_LONGITUDE]}_{fire_data[ATTR_ACQ_DATE]}_{fire_data[ATTR_ACQ_TIME]}"
        
    @property
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        lat = round(self._fire_data[ATTR_LATITUDE], 2)
        lon = round(self._fire_data[ATTR_LONGITUDE], 2)
        confidence = self._fire_data[ATTR_CONFIDENCE_NAME]
        return f"{confidence} conf Fire NASA FIRMS ({lat}, {lon})"

    @property
    def state(self):
        return round(self._fire_data[ATTR_DISTANCE], 1)

    @property
    def source(self):
        return DOMAIN

    @property
    def latitude(self):
        return self._fire_data[ATTR_LATITUDE]

    @property
    def longitude(self):
        return self._fire_data[ATTR_LONGITUDE]

    @property
    def unit_of_measurement(self):
        return self._fire_data.get(ATTR_UNIT, "km")

    @property
    def icon(self):
        confidence_level = self._fire_data.get(ATTR_CONFIDENCE_LEVEL, "l")
        return CONFIDENCE_LEVELS.get(confidence_level, {}).get("icon", "mdi:fire-off")

    @property
    def extra_state_attributes(self):
        return {
            ATTR_LATITUDE: self._fire_data[ATTR_LATITUDE],
            ATTR_LONGITUDE: self._fire_data[ATTR_LONGITUDE],
            ATTR_BRIGHT_TI4: self._fire_data[ATTR_BRIGHT_TI4],
            ATTR_BRIGHT_TI5: self._fire_data[ATTR_BRIGHT_TI5],
            ATTR_SCAN: self._fire_data[ATTR_SCAN],
            ATTR_TRACK: self._fire_data[ATTR_TRACK],
            ATTR_ACQ_DATE: self._fire_data[ATTR_ACQ_DATE],
            ATTR_ACQ_TIME: self._fire_data[ATTR_ACQ_TIME],
            ATTR_ACQ_LOCAL_TIME: self._fire_data[ATTR_ACQ_LOCAL_TIME],
            ATTR_ACQ_LOCAL_DATE: self._fire_data[ATTR_ACQ_LOCAL_DATE],
            ATTR_SATELLITE: self._fire_data[ATTR_SATELLITE],
            ATTR_INSTRUMENT: self._fire_data[ATTR_INSTRUMENT],
            ATTR_CONFIDENCE: self._fire_data[ATTR_CONFIDENCE],
            ATTR_CONFIDENCE_LEVEL: self._fire_data[ATTR_CONFIDENCE_LEVEL],
            ATTR_CONFIDENCE_NAME: self._fire_data[ATTR_CONFIDENCE_NAME],
            ATTR_VERSION: self._fire_data[ATTR_VERSION],
            ATTR_FRP: self._fire_data[ATTR_FRP],
            ATTR_DAYNIGHT: self._fire_data[ATTR_DAYNIGHT],
            ATTR_DISTANCE_KM: round(self._fire_data[ATTR_DISTANCE_KM], 1),
            "attribution": ATTRIBUTION,
            "integration_version": VERSION,
        }

    @callback
    def _handle_coordinator_update(self):
        for fire in self.coordinator.data or []:
            if (
                fire[ATTR_LATITUDE] == self._fire_data[ATTR_LATITUDE]
                and fire[ATTR_LONGITUDE] == self._fire_data[ATTR_LONGITUDE]
                and fire[ATTR_ACQ_DATE] == self._fire_data[ATTR_ACQ_DATE]
            ):
                self._fire_data = fire
                super()._handle_coordinator_update()
                return
        self.hass.async_create_task(self.async_remove(force_remove=True))