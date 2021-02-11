"""Support for climacell.co"""

import logging
import re
import pytz
from datetime import datetime

from custom_components.climacell.global_const import *
from custom_components.climacell.schema_const import SCHEMA_EXTENSION

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

from . import DOMAIN, ClimacellTimelineDataProvider
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from custom_components.climacell.lib import prepare_config

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SCHEMA_EXTENSION)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Climacell sensor."""
    
    _LOGGER.info("__init__ setup_platform 'sensor' start for %s.", DOMAIN)

    config = prepare_config(hass, config)
    
    sensors = []
    for timeline_spec in config[CONF_TIMELINES]:
        observations = timeline_spec[CONF_FORECAST_OBSERVATIONS]
        data_provider = ClimacellTimelineDataProvider(
            api_key=config.get(CONF_API_KEY),
            latitude=config.get(CONF_LATITUDE),
            longitude=config.get(CONF_LONGITUDE),
            interval=timeline_spec[CONF_SCAN_INTERVAL],
            units=config.get(CONF_UNITS),
            fields=timeline_spec[CONF_FIELDS].keys(),
            start_time=timeline_spec[CONF_START_TIME],
            observations=observations,
            timesteps=timeline_spec[CONF_TIMESTEP],
            exceptions=timeline_spec[CONF_EXCLUDE_INTERVAL],
        )

        data_provider.retrieve_update()

        for field in timeline_spec[CONF_FIELDS]:
            field_values = timeline_spec[CONF_FIELDS][field]
            for observation in range(0, observations):
                sensors.append(
                    ClimacellTimelineSensor(
                        data_provider=data_provider,
                        field=field,
                        condition_name=field_values[ATTR_CONDITION],
                        sensor_friendly_name=timeline_spec[CONF_NAME]
                        + " "
                        + field_values[ATTR_NAME],
                        timestep=timeline_spec[CONF_TIMESTEP],
                        observation=None if observations == 1 else observation,
                        update=timeline_spec[CONF_UPDATE],
                        unit=field_values[ATTR_UNIT_OF_MEASUREMENT],
                        icon=field_values[ATTR_ICON],
                    )
                )
    add_entities(sensors, True)

    _LOGGER.info("__init__ setup_platform 'sensor' done for %s.", DOMAIN)
    return True

class ClimacellTimelineSensor(Entity):
    def __init__(
        self,
        data_provider,
        field,
        condition_name,
        sensor_friendly_name,
        timestep,
        observation,
        update,
        unit,
        icon,
    ):
        self.__data_provider = data_provider
        self.__field = field
        self._condition_name = condition_name
        self._observation = observation
        self.__update = update
        self.__icon = icon

        self.__friendly_name = "cc " + sensor_friendly_name

        if timestep == 'current':
            self._observation = 0
        else:
            timestep_suffix = timestep[-1]
            timestep_int = int(timestep[:-1])
            timestep_length = 1
            if timestep_suffix == "m":
                timestep_length = 2

            if self._observation is None:
                timestep_formatted = ""
            else:
                timestep_formatted = (
                    str(timestep_int * (self._observation)).zfill(timestep_length)
                    + timestep_suffix
                )

            self.__friendly_name += " " + timestep_formatted

        if isinstance(unit, dict):
            self._unit_of_measurement = None
            self.__valuemap = unit
        elif unit is None:
            self._unit_of_measurement = None
            self.__valuemap = None
        else:
            self._unit_of_measurement = unit
            self.__valuemap = None

        self._state = None
        self._observation_time = None

    @staticmethod
    def __to_float(value):
        if type(value) == str:
            if re.match(r"^-?\d+(?:\.\d+)?$", value) is None:
                return value
            elif re.search("^[1-9][0-9]{0,2}(?:,[0-9]{3}){0,3}$", value):
                return int(value)
            else:
                return float(value)
        else:
            return value

    @property
    def name(self):
        """Return the name of the sensor."""
        return self.__friendly_name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.__icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.__to_float(self._state)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_OBSERVATION_TIME: self._observation_time,
            ATTR_UNIT_OF_MEASUREMENT: self._unit_of_measurement,
        }

        return attrs

    def update(self):
        if ATTR_AUTO == self.__update:
            self.__data_provider.retrieve_update()

        if self.__data_provider.data is not None:
            if (0 if self._observation is None else self._observation) >= len(self.__data_provider.data["intervals"]):
                _LOGGER.error(
                    "observation %s missing: %s",
                    self._observation,
                    self.__data_provider.data,
                )
                return

            sensor_data = self.__data_provider.data["intervals"][(0 if self._observation is None else self._observation)]
            self._state = sensor_data["values"][self.__field]
            if self.__valuemap is not None:
                self._state = self.__valuemap[str(self._state)]

            self._observation_time = sensor_data["startTime"]
            try:
                dt = datetime.strptime(self._observation_time, "%Y-%m-%dT%H:%M:%S.%fZ")
                utc = dt.replace(tzinfo=pytz.timezone("UTC"), microsecond=0, second=0)
                local_dt = utc.astimezone(self.hass.config.time_zone)
                self._observation_time = local_dt.isoformat()
            except Exception as e:
                pass

        else:
            _LOGGER.warning(
                "TimelineSensor.update - Provider has no data for: %s", self.name
            )
