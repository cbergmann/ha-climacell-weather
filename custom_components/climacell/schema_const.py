import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from custom_components.climacell.global_const import *

from homeassistant.components.google_assistant import CONF_API_KEY
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_MONITORED_CONDITIONS,
    ATTR_ICON,
    ATTR_ATTRIBUTION,
    ATTR_UNIT_OF_MEASUREMENT,
    ATTR_NAME,
)
from custom_components.climacell.daily_api_const import (
    CONF_DAILY,
    SCHEMA_DAILY_CONDITIONS,
)
from custom_components.climacell.hourly_api_const import (
    CONF_HOURLY,
    SCHEMA_HOURLY_CONDITIONS,
)
from custom_components.climacell.nowcast_api_const import (
    SCHEMA_NOWCAST_CONDITIONS,
    CONF_NOWCAST,
)
from custom_components.climacell.realtime_api_const import (
    CONF_REALTIME,
    SCHEMA_REALTIME_CONDITIONS,
)
MONITORED_CONDITIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_REALTIME): vol.Schema(SCHEMA_REALTIME_CONDITIONS),
        vol.Optional(CONF_DAILY): vol.Schema(SCHEMA_DAILY_CONDITIONS),
        vol.Optional(CONF_HOURLY): vol.Schema(SCHEMA_HOURLY_CONDITIONS),
        vol.Optional(CONF_NOWCAST): vol.Schema(SCHEMA_NOWCAST_CONDITIONS),
    }
)

SCHEMA_TIMELINE = vol.Schema(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_FIELDS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_FORECAST_OBSERVATIONS): cv.positive_int,
        vol.Optional(CONF_UPDATE): vol.All(cv.ensure_list, [vol.In(UPDATE_MODES)]),
        vol.Optional(CONF_EXCLUDE_INTERVAL): vol.All(
            cv.ensure_list, [vol.Schema(SCHEMA_EXCLUDE_INTERVAL)]
        ),
        vol.Optional(CONF_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_TIMESTEP, default="1d"): cv.string,
        vol.Optional(CONF_START_TIME, default=0): vol.Coerce(int),
    }
)

SCHEMA_EXTENSION = {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME.lower()): cv.string,
        vol.Optional(CONF_UNITS): vol.In(CONF_ALLOWED_UNITS + CONF_LEGACY_UNITS),
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.Schema(
            MONITORED_CONDITIONS_SCHEMA
        ),
        vol.Optional(CONF_TIMELINES, default=[]): vol.All(
            cv.ensure_list, [vol.Schema(SCHEMA_TIMELINE)]
        ),
    }

