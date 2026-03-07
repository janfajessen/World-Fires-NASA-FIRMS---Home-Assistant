"""Flujo de configuración para NASA FIRMS Fires."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    VERSION,
    CONF_API_KEY,
    CONF_RADIUS_KM,
    CONF_UNITS,
    CONF_MIN_CONFIDENCE,
    CONF_DAYS,
    CONF_SOURCE,
    CONF_SCAN_INTERVAL,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEFAULT_RADIUS_KM,
    DEFAULT_UNITS,
    DEFAULT_MIN_CONFIDENCE,
    DEFAULT_DAYS,
    DEFAULT_SOURCE,
    DEFAULT_SCAN_INTERVAL,
    MIN_DAYS,
    MAX_DAYS,
    MIN_RADIUS,
    MAX_RADIUS,
    MIN_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
)

class FirmsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        
        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY, "")
            
            if len(api_key) < 10:
                errors[CONF_API_KEY] = "api_key_invalid"
            else:
                data = {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_LATITUDE: user_input[CONF_LATITUDE],
                    CONF_LONGITUDE: user_input[CONF_LONGITUDE],
                }
                options = {
                    CONF_RADIUS_KM: user_input[CONF_RADIUS_KM],
                    CONF_UNITS: user_input.get(CONF_UNITS, DEFAULT_UNITS),
                    CONF_MIN_CONFIDENCE: user_input.get(CONF_MIN_CONFIDENCE, DEFAULT_MIN_CONFIDENCE),
                    CONF_SOURCE: user_input.get(CONF_SOURCE, DEFAULT_SOURCE),
                    CONF_DAYS: user_input.get(CONF_DAYS, DEFAULT_DAYS),
                    CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                }
                return self.async_create_entry(
                    title="NASA FIRMS Fires",
                    data=data,
                    options=options
                )

        data_schema = vol.Schema({
            vol.Required(CONF_API_KEY): selector.TextSelector(
                selector.TextSelectorConfig(
                    type=selector.TextSelectorType.PASSWORD,
                )
            ),
            vol.Required(CONF_LATITUDE, default=self.hass.config.latitude): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-90,
                    max=90,
                    step=0.001,
                    mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_LONGITUDE, default=self.hass.config.longitude): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=-180,
                    max=180,
                    step=0.001,
                    mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_RADIUS_KM, default=DEFAULT_RADIUS_KM): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_RADIUS,
                    max=MAX_RADIUS,
                    unit_of_measurement="km",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Optional(CONF_UNITS, default=DEFAULT_UNITS): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "km", "label": "units_km"},
                        {"value": "mi", "label": "units_mi"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="units"
                )
            ),
            vol.Optional(CONF_MIN_CONFIDENCE, default=DEFAULT_MIN_CONFIDENCE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "l", "label": "confidence_l"},
                        {"value": "n", "label": "confidence_n"},
                        {"value": "h", "label": "confidence_h"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="confidence"
                )
            ),
            vol.Optional(CONF_SOURCE, default=DEFAULT_SOURCE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "VIIRS_SNPP_NRT", "label": "source_viirs"},
                        {"value": "MODIS_NRT", "label": "source_modis"},
                        {"value": "VIIRS_NOAA20_NRT", "label": "source_viirs_noaa"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="source"
                )
            ),
            vol.Optional(CONF_DAYS, default=DEFAULT_DAYS): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_DAYS,
                    max=MAX_DAYS,
                    unit_of_measurement="days_unit",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    unit_of_measurement="minutes_unit",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )  # Sin description_placeholders

    @staticmethod
    def async_get_options_flow(config_entry):
        return FirmsOptionsFlow(config_entry)

class FirmsOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_RADIUS_KM, default=self.config_entry.options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_RADIUS,
                    max=MAX_RADIUS,
                    unit_of_measurement="km",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(CONF_UNITS, default=self.config_entry.options.get(CONF_UNITS, DEFAULT_UNITS)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "km", "label": "units_km"},
                        {"value": "mi", "label": "units_mi"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="units"
                )
            ),
            vol.Required(CONF_MIN_CONFIDENCE, default=self.config_entry.options.get(CONF_MIN_CONFIDENCE, DEFAULT_MIN_CONFIDENCE)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "l", "label": "confidence_l"},
                        {"value": "n", "label": "confidence_n"},
                        {"value": "h", "label": "confidence_h"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="confidence"
                )
            ),
            vol.Required(CONF_SOURCE, default=self.config_entry.options.get(CONF_SOURCE, DEFAULT_SOURCE)): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "VIIRS_SNPP_NRT", "label": "source_viirs"},
                        {"value": "MODIS_NRT", "label": "source_modis"},
                        {"value": "VIIRS_NOAA20_NRT", "label": "source_viirs_noaa"}
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="source"
                )
            ),
            vol.Required(CONF_DAYS, default=self.config_entry.options.get(CONF_DAYS, DEFAULT_DAYS)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_DAYS,
                    max=MAX_DAYS,
                    unit_of_measurement="days_unit",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
            vol.Required(CONF_SCAN_INTERVAL, default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_SCAN_INTERVAL,
                    max=MAX_SCAN_INTERVAL,
                    unit_of_measurement="minutes_unit",
                    mode=selector.NumberSelectorMode.SLIDER
                )
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )