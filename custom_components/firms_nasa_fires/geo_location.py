"""Plataforma geo_location para NASA FIRMS Fires."""
import logging
import asyncio
from datetime import timedelta, datetime
import csv
from io import StringIO
import math

import aiohttp
from haversine import haversine, Unit
from zoneinfo import ZoneInfo

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
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
    CONF_DAYNIGHT,
    CONF_DATE,
    CONF_MIN_FRP,
    DEFAULT_MIN_FRP,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SOURCE,
    DEFAULT_DAYNIGHT,
    DEFAULT_DATE,
    CONFIDENCE_LEVELS,
    KM_TO_MILES,
    FIRMS_API_URL,
    FIRMS_API_URL_DATE,
    ATTRIBUTION,
    MODIS_SOURCES,
    DEDUP_RADIUS_KM,
    DEDUP_TIME_WINDOW_MIN,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_BRIGHT_TI4,
    ATTR_BRIGHT_TI5,
    ATTR_BRIGHTNESS,
    ATTR_BRIGHT_T31,
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
    ATTR_SOURCE,
    EVENT_NEW_FIRE,
    ATTR_LOCATION_NAME,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_sources(entry) -> list[str]:
    """Devuelve siempre una lista de fuentes aunque sea un string heredado."""
    raw = entry.options.get(CONF_SOURCE, DEFAULT_SOURCE)
    if isinstance(raw, str):
        return [raw]
    return list(raw)


def get_confidence_level(confidence_value) -> str:
    """Normaliza cualquier valor de confianza a 'l', 'n' o 'h'."""
    if confidence_value is None:
        return "l"
    conf_str = str(confidence_value).lower().strip()
    if conf_str in ("l", "n", "h"):
        return conf_str
    try:
        conf_num = int(float(conf_str))
        if conf_num <= 30:
            return "l"
        elif conf_num <= 65:
            return "n"
        else:
            return "h"
    except Exception:
        return "l"


def _parse_acq_minutes(acq_time: str) -> int:
    """Convierte el campo acq_time (p.ej. '1253') a minutos desde medianoche."""
    try:
        t = acq_time.zfill(4)
        return int(t[:2]) * 60 + int(t[2:])
    except Exception:
        return 0


def _deduplicate(fires: list[dict]) -> list[dict]:
    """
    Elimina detecciones duplicadas del mismo incendio por distintos satélites.

    Dos fuegos se consideran el mismo si:
      - Están a menos de DEDUP_RADIUS_KM entre sí, Y
      - Mismo día de adquisición, Y
      - Diferencia de hora < DEDUP_TIME_WINDOW_MIN.

    Se conserva el de mayor confianza; en empate, el de mayor FRP.
    """
    if not fires:
        return fires

    confidence_rank = {"l": 1, "n": 2, "h": 3}
    kept: list[dict] = []

    for fire in fires:
        merged = False
        for i, existing in enumerate(kept):
            dist = haversine(
                (existing[ATTR_LATITUDE], existing[ATTR_LONGITUDE]),
                (fire[ATTR_LATITUDE],     fire[ATTR_LONGITUDE]),
                unit=Unit.KILOMETERS,
            )
            if dist > DEDUP_RADIUS_KM:
                continue
            if existing[ATTR_ACQ_DATE] != fire[ATTR_ACQ_DATE]:
                continue
            time_diff = abs(
                _parse_acq_minutes(existing[ATTR_ACQ_TIME])
                - _parse_acq_minutes(fire[ATTR_ACQ_TIME])
            )
            if time_diff > DEDUP_TIME_WINDOW_MIN:
                continue

            existing_rank = confidence_rank.get(existing[ATTR_CONFIDENCE_LEVEL], 1)
            fire_rank = confidence_rank.get(fire[ATTR_CONFIDENCE_LEVEL], 1)
            if fire_rank > existing_rank or (
                fire_rank == existing_rank and fire[ATTR_FRP] > existing[ATTR_FRP]
            ):
                kept[i] = fire
            merged = True
            break

        if not merged:
            kept.append(fire)

    return kept


def _local_datetime(acq_date: str, acq_time: str, tz_name: str):
    """Convierte fecha+hora UTC a hora local. Devuelve (date_str, time_str)."""
    if not acq_date or not acq_time:
        return "", ""
    try:
        t = acq_time.zfill(4)
        acq_utc = datetime.strptime(
            f"{acq_date} {t[:2]}:{t[2:]}:00", "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=ZoneInfo("UTC"))
        local = acq_utc.astimezone(ZoneInfo(tz_name))
        return local.strftime("%d-%m-%Y"), local.strftime("%H:%M")
    except Exception:
        return "", ""


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

async def async_setup_entry(hass, entry, async_add_entities):
    # El coordinator ya fue creado y almacenado en __init__.py
    # antes de que esta plataforma arranque.
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    # Set local de sesión: empieza vacío en cada carga.
    # Evita que el entity registry persistente bloquee la recreación tras reload.
    added_unique_ids: set[str] = set()

    async def _add_new_entities():
        new_entities = []
        for fire_data in coordinator.data or []:
            unique_id = _make_unique_id(fire_data)
            if unique_id not in added_unique_ids:
                added_unique_ids.add(unique_id)
                new_entities.append(FirmsGeolocation(fire_data, coordinator, entry))
        if new_entities:
            async_add_entities(new_entities)

    await _add_new_entities()
    entry.async_on_unload(
        coordinator.async_add_listener(
            lambda: hass.async_create_task(_add_new_entities())
        )
    )
    return True


def _make_unique_id(fire_data: dict) -> str:
    return (
        f"{fire_data[ATTR_CONFIDENCE_LEVEL]}_conf_fire_nasa_firms_"
        f"{fire_data[ATTR_LATITUDE]}_{fire_data[ATTR_LONGITUDE]}_"
        f"{fire_data[ATTR_ACQ_DATE]}_{fire_data[ATTR_ACQ_TIME]}"
    )


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------

class FirmsDataUpdateCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.entry = entry
        self._previous_ids: set[str] = set()
        self.last_firms_update: str | None = None
        self._geocode_cache: dict[tuple, str] = {}  # Cache (lat,lon) → nombre lugar

    async def _async_update_data(self):
        api_key   = self.entry.data[CONF_API_KEY]
        radius    = float(self.entry.options[CONF_RADIUS_KM])
        units     = self.entry.options[CONF_UNITS]
        min_conf  = self.entry.options[CONF_MIN_CONFIDENCE]
        days      = int(self.entry.options[CONF_DAYS])
        sources   = _get_sources(self.entry)
        home_lat  = float(self.entry.data[CONF_LATITUDE])
        home_lon  = float(self.entry.data[CONF_LONGITUDE])
        daynight  = self.entry.options.get(CONF_DAYNIGHT, DEFAULT_DAYNIGHT)
        date_str  = (self.entry.options.get(CONF_DATE) or "").strip()
        min_frp   = float(self.entry.options.get(CONF_MIN_FRP, DEFAULT_MIN_FRP))

        # Bounding box
        lat_off = radius / 111.0
        lon_off = radius / (111.0 * abs(math.cos(math.radians(home_lat))) + 0.01)
        bbox = (
            f"{home_lon - lon_off},{home_lat - lat_off},"
            f"{home_lon + lon_off},{home_lat + lat_off}"
        )

        confidence_rank = {"l": 1, "n": 2, "h": 3}
        min_rank = confidence_rank.get(min_conf, 1)

        async with aiohttp.ClientSession() as session:
            tasks = [
                self._fetch_source(
                    session, api_key, src, bbox, days, date_str,
                    home_lat, home_lon, radius, units, min_rank, daynight, min_frp,
                )
                for src in sources
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        all_fires: list[dict] = []
        for src, result in zip(sources, results):
            if isinstance(result, Exception):
                _LOGGER.error("Error fetching source %s: %s", src, result)
            else:
                all_fires.extend(result)

        if not all_fires and all(isinstance(r, Exception) for r in results):
            raise UpdateFailed("All FIRMS sources failed to fetch data.")

        if len(sources) > 1:
            before = len(all_fires)
            all_fires = _deduplicate(all_fires)
            _LOGGER.debug(
                "FIRMS dedup: %d → %d fires after cross-satellite deduplication",
                before, len(all_fires),
            )

        all_fires.sort(key=lambda x: x[ATTR_DISTANCE])
        _LOGGER.debug(
            "FIRMS update complete: %d fires (sources: %s, daynight: %s, date: %s)",
            len(all_fires), sources, daynight, date_str or "latest",
        )

        # Geocodificación inversa — 1 llamada/segundo (límite Nominatim)
        lang = self.hass.config.language or "en"
        _LOGGER.warning("FIRMS geocoding: starting for %d fires (lang=%s)", len(all_fires), lang)
        all_fires = await self._geocode_fires(all_fires, lang)
        _LOGGER.warning("FIRMS geocoding: completed")

        # Disparar evento en el bus de HA por cada incendio nuevo detectado
        # (no existía en el update anterior)
        current_ids = {_make_unique_id(f) for f in all_fires}
        for fire in all_fires:
            uid = _make_unique_id(fire)
            if uid not in self._previous_ids:
                self.hass.bus.async_fire(
                    EVENT_NEW_FIRE,
                    {
                        "entry_id": self.entry.entry_id,
                        ATTR_LATITUDE:       fire[ATTR_LATITUDE],
                        ATTR_LONGITUDE:      fire[ATTR_LONGITUDE],
                        ATTR_DISTANCE_KM:    round(fire[ATTR_DISTANCE_KM], 1),
                        ATTR_DISTANCE:       round(fire[ATTR_DISTANCE], 1),
                        ATTR_UNIT:           fire[ATTR_UNIT],
                        ATTR_CONFIDENCE_LEVEL: fire[ATTR_CONFIDENCE_LEVEL],
                        ATTR_CONFIDENCE_NAME:  fire[ATTR_CONFIDENCE_NAME],
                        ATTR_FRP:            fire[ATTR_FRP],
                        ATTR_DAYNIGHT:       fire[ATTR_DAYNIGHT],
                        ATTR_SOURCE:         fire[ATTR_SOURCE],
                        ATTR_ACQ_DATE:       fire[ATTR_ACQ_DATE],
                        ATTR_ACQ_LOCAL_DATE: fire[ATTR_ACQ_LOCAL_DATE],
                        ATTR_ACQ_LOCAL_TIME: fire[ATTR_ACQ_LOCAL_TIME],
                        ATTR_LOCATION_NAME:  fire.get(ATTR_LOCATION_NAME, ""),
                    },
                )
        self._previous_ids = current_ids

        # Guardar timestamp del update completado en hora local
        from datetime import datetime
        self.last_firms_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return all_fires

    async def _geocode_fires(self, fires: list[dict], lang: str) -> list[dict]:
        """
        Geocodificación inversa de cada fuego usando Nominatim (OpenStreetMap).
        Respeta el límite de 1 petición/segundo de Nominatim.
        Usa cache interno para no repetir coordenadas ya vistas.
        El resultado se añade como atributo ATTR_LOCATION_NAME a cada fuego.
        """
        headers = {
            "User-Agent": f"{DOMAIN}/2.3 (Home Assistant custom integration; "
                          "https://github.com/janfajessen/Fires-NASA-FIRMS-Unofficial)"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            for fire in fires:
                lat = round(fire[ATTR_LATITUDE], 2)   # ~1 km de precisión para cache
                lon = round(fire[ATTR_LONGITUDE], 2)
                cache_key = (lat, lon)

                if cache_key in self._geocode_cache:
                    fire[ATTR_LOCATION_NAME] = self._geocode_cache[cache_key]
                    continue

                try:
                    url = (
                        f"https://nominatim.openstreetmap.org/reverse"
                        f"?lat={lat}&lon={lon}&format=json&accept-language={lang}"
                    )
                    async with asyncio.timeout(10):
                        async with session.get(url) as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                addr = data.get("address", {})
                                city = (
                                    addr.get("city")
                                    or addr.get("town")
                                    or addr.get("village")
                                    or addr.get("hamlet")
                                    or addr.get("municipality")
                                    or ""
                                )
                                state = addr.get("state") or addr.get("county") or ""
                                country = addr.get("country") or ""
                                location = ", ".join(p for p in [city, state, country] if p)
                            else:
                                location = ""
                except Exception as exc:
                    _LOGGER.warning("FIRMS geocoding error for (%s, %s): %s", lat, lon, exc)
                    location = ""

                fire[ATTR_LOCATION_NAME] = location
                self._geocode_cache[cache_key] = location
                await asyncio.sleep(1)   # Límite Nominatim: 1 req/s

        return fires

    async def _fetch_source(
        self, session, api_key, source, bbox, days, date_str,
        home_lat, home_lon, radius, units, min_rank, daynight, min_frp: float = 0,
    ) -> list[dict]:
        # Modo fecha histórica o modo "últimos N días"
        if date_str:
            url = FIRMS_API_URL_DATE.format(
                api_key=api_key, source=source, bbox=bbox, date=date_str
            )
        else:
            url = FIRMS_API_URL.format(
                api_key=api_key, source=source, bbox=bbox, days=days
            )

        _LOGGER.debug("Fetching FIRMS source %s: %s", source, url)

        confidence_rank = {"l": 1, "n": 2, "h": 3}
        is_modis = source in MODIS_SOURCES

        async with asyncio.timeout(30):
            async with session.get(url) as response:
                if response.status != 200:
                    text = await response.text()
                    raise UpdateFailed(f"HTTP {response.status} for {source}: {text}")
                text_data = await response.text()

        # Si la respuesta no es CSV válido (ej: mensaje de error, rate limit),
        # lo logamos a nivel WARNING para que sea visible sin debug mode.
        first_line = text_data.strip().split("\n")[0] if text_data.strip() else ""
        if first_line and "latitude" not in first_line.lower():
            _LOGGER.warning(
                "FIRMS API returned unexpected response for %s (first line: %r). "
                "Check your API key and rate limits.",
                source, first_line[:200],
            )
            return []

        rows_total = 0
        rows_filtered = 0
        filtered_confidence = 0
        filtered_daynight = 0
        filtered_frp = 0

        fires = []
        for row in csv.DictReader(StringIO(text_data)):
            rows_total += 1
            try:
                fire_lat = float(row["latitude"])
                fire_lon = float(row["longitude"])

                distance_km = haversine(
                    (home_lat, home_lon), (fire_lat, fire_lon),
                    unit=Unit.KILOMETERS,
                )
                if distance_km > radius:
                    rows_filtered += 1
                    continue

                conf_level = get_confidence_level(row.get("confidence"))
                if confidence_rank.get(conf_level, 1) < min_rank:
                    filtered_confidence += 1
                    continue

                # Filtro día/noche — "all" no filtra nada
                row_daynight = row.get("daynight", "")
                if daynight != "all" and row_daynight and row_daynight != daynight:
                    filtered_daynight += 1
                    continue

                # Filtro FRP mínimo — elimina falsos positivos industriales
                # 0 = sin filtro (comportamiento por defecto)
                fire_frp = float(row.get("frp", 0) or 0)
                if min_frp > 0 and fire_frp < min_frp:
                    filtered_frp += 1
                    continue

                distance = distance_km * KM_TO_MILES if units == "mi" else distance_km

                acq_date = row.get("acq_date", "")
                acq_time = row.get("acq_time", "")
                local_date, local_time = _local_datetime(
                    acq_date, acq_time, self.hass.config.time_zone
                )

                # Campos de brillo: MODIS/Landsat usan campos distintos a VIIRS
                if is_modis:
                    bright_primary   = float(row.get("brightness", 0) or 0)
                    bright_secondary = float(row.get("bright_t31", 0) or 0)
                else:
                    bright_primary   = float(row.get("bright_ti4", 0) or 0)
                    bright_secondary = float(row.get("bright_ti5", 0) or 0)

                fires.append({
                    ATTR_LATITUDE:         fire_lat,
                    ATTR_LONGITUDE:        fire_lon,
                    ATTR_BRIGHT_TI4:       bright_primary,
                    ATTR_BRIGHT_TI5:       bright_secondary,
                    ATTR_BRIGHTNESS:       bright_primary,
                    ATTR_BRIGHT_T31:       bright_secondary if is_modis else 0,
                    ATTR_SCAN:             float(row.get("scan",  0) or 0),
                    ATTR_TRACK:            float(row.get("track", 0) or 0),
                    ATTR_ACQ_DATE:         acq_date,
                    ATTR_ACQ_TIME:         acq_time,
                    ATTR_ACQ_LOCAL_TIME:   local_time,
                    ATTR_ACQ_LOCAL_DATE:   local_date,
                    ATTR_SATELLITE:        row.get("satellite",  ""),
                    ATTR_INSTRUMENT:       row.get("instrument", ""),
                    ATTR_CONFIDENCE:       row.get("confidence", ""),
                    ATTR_CONFIDENCE_LEVEL: conf_level,
                    ATTR_CONFIDENCE_NAME:  CONFIDENCE_LEVELS[conf_level]["name"],
                    ATTR_VERSION:          row.get("version",    ""),
                    ATTR_FRP:              float(row.get("frp",  0) or 0),
                    ATTR_DAYNIGHT:         row_daynight,
                    ATTR_DISTANCE_KM:      distance_km,
                    ATTR_DISTANCE:         distance,
                    ATTR_UNIT:             units,
                    ATTR_SOURCE:           source,
                })
            except Exception as exc:
                _LOGGER.debug("Error processing FIRMS row: %s", exc)

        _LOGGER.warning(
            "FIRMS source %s: %d rows in CSV, %d outside radius, "
            "%d filtered by confidence (min_rank=%d), %d filtered by daynight (filter=%s), "
            "%d filtered by FRP (min=%.1f MW), %d fires kept",
            source, rows_total, rows_filtered,
            filtered_confidence, min_rank,
            filtered_daynight, daynight,
            filtered_frp, min_frp,
            len(fires),
        )
        return fires


# ---------------------------------------------------------------------------
# Entidad geo_location
# ---------------------------------------------------------------------------

class FirmsGeolocation(CoordinatorEntity, GeolocationEvent):
    _attr_should_poll = False

    def __init__(self, fire_data, coordinator, entry):
        super().__init__(coordinator)
        self._fire_data = fire_data
        self._entry = entry
        self._unique_id = _make_unique_id(fire_data)

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
    def unique_id(self):
        return self._unique_id

    @property
    def name(self):
        lat = round(self._fire_data[ATTR_LATITUDE],  2)
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
        level = self._fire_data.get(ATTR_CONFIDENCE_LEVEL, "l")
        return CONFIDENCE_LEVELS.get(level, {}).get("icon", "mdi:fire-off")

    @property
    def extra_state_attributes(self):
        fd = self._fire_data
        return {
            ATTR_LATITUDE:         fd[ATTR_LATITUDE],
            ATTR_LONGITUDE:        fd[ATTR_LONGITUDE],
            ATTR_BRIGHTNESS:       fd[ATTR_BRIGHTNESS],
            ATTR_BRIGHT_TI4:       fd[ATTR_BRIGHT_TI4],
            ATTR_BRIGHT_TI5:       fd[ATTR_BRIGHT_TI5],
            ATTR_BRIGHT_T31:       fd[ATTR_BRIGHT_T31],
            ATTR_SCAN:             fd[ATTR_SCAN],
            ATTR_TRACK:            fd[ATTR_TRACK],
            ATTR_ACQ_DATE:         fd[ATTR_ACQ_DATE],
            ATTR_ACQ_TIME:         fd[ATTR_ACQ_TIME],
            ATTR_ACQ_LOCAL_TIME:   fd[ATTR_ACQ_LOCAL_TIME],
            ATTR_ACQ_LOCAL_DATE:   fd[ATTR_ACQ_LOCAL_DATE],
            ATTR_SATELLITE:        fd[ATTR_SATELLITE],
            ATTR_INSTRUMENT:       fd[ATTR_INSTRUMENT],
            ATTR_CONFIDENCE:       fd[ATTR_CONFIDENCE],
            ATTR_CONFIDENCE_LEVEL: fd[ATTR_CONFIDENCE_LEVEL],
            ATTR_CONFIDENCE_NAME:  fd[ATTR_CONFIDENCE_NAME],
            ATTR_VERSION:          fd[ATTR_VERSION],
            ATTR_FRP:              fd[ATTR_FRP],
            ATTR_DAYNIGHT:         fd[ATTR_DAYNIGHT],
            ATTR_DISTANCE_KM:      round(fd[ATTR_DISTANCE_KM], 1),
            ATTR_SOURCE:           fd[ATTR_SOURCE],
            ATTR_LOCATION_NAME:    fd.get(ATTR_LOCATION_NAME, ""),
            "attribution":         ATTRIBUTION,
            "integration_version": VERSION,
        }

    @callback
    def _handle_coordinator_update(self):
        """Actualizar datos cuando el coordinador refresca."""
        for fire in self.coordinator.data or []:
            if (
                fire[ATTR_LATITUDE]  == self._fire_data[ATTR_LATITUDE]
                and fire[ATTR_LONGITUDE] == self._fire_data[ATTR_LONGITUDE]
                and fire[ATTR_ACQ_DATE]  == self._fire_data[ATTR_ACQ_DATE]
            ):
                self._fire_data = fire
                super()._handle_coordinator_update()
                return
        self.hass.async_create_task(self.async_remove())
