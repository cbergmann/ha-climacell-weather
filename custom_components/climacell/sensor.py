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
from custom_components.climacell.daily_api_const import (
    CONF_DAILY,
)
from custom_components.climacell.hourly_api_const import (
    CONF_HOURLY,
)
from custom_components.climacell.nowcast_api_const import (
    CONF_NOWCAST,
)
from custom_components.climacell.realtime_api_const import (
    CONF_REALTIME,
)

from . import DOMAIN, ClimacellTimelineDataProvider
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(SCHEMA_EXTENSION)

def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Climacell sensor."""
    _LOGGER.info(
        "__init__ setup_platform 'sensor' start for %s with config %s.", DOMAIN, config
    )

    _LOGGER.info("__init__ setup_platform 'sensor' start for %s.", DOMAIN)

    config.setdefault(CONF_NAME, DEFAULT_NAME.lower())
    config.setdefault(CONF_LATITUDE, hass.config.latitude)
    config.setdefault(CONF_LONGITUDE, hass.config.longitude)

    if CONF_UNITS in config:
        units = config[CONF_UNITS]
    elif hass.config.units.is_metric:
        units = CONF_ALLOWED_UNITS[0]
    else:
        units = CONF_ALLOWED_UNITS[1]

    if units == CONF_LEGACY_UNITS[0]:
        units = CONF_ALLOWED_UNITS[0]
    elif units == CONF_LEGACY_UNITS[1]:
        units = CONF_ALLOWED_UNITS[1]
        
    config[CONF_UNITS] = units

    LEGACY_CONF_TIMESTEPS = {
        CONF_REALTIME: "1m",
        CONF_DAILY: "1d",
        CONF_HOURLY: "1h",
        CONF_NOWCAST: "5m",
    }

    config.setdefault(CONF_TIMELINES,[])

    if CONF_MONITORED_CONDITIONS in config:
        for key in LEGACY_CONF_TIMESTEPS:
            if key in config[CONF_MONITORED_CONDITIONS]:
                leg_conf = config[CONF_MONITORED_CONDITIONS][key]

                default_observations = 1 if key == CONF_REALTIME else 5

                leg_observations = (
                    leg_conf[CONF_FORECAST_OBSERVATIONS][0]
                    if CONF_FORECAST_OBSERVATIONS in leg_conf
                    else default_observations
                )
                leg_interval = leg_conf.get(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL)
                leg_exclude = leg_conf.get(CONF_EXCLUDE_INTERVAL,None)
                leg_update = (
                    leg_conf[CONF_UPDATE][0] if CONF_UPDATE in leg_conf else ATTR_AUTO
                )
                leg_timestep = (
                    str(leg_conf[CONF_TIMESTEP][0]) + "m"
                    if CONF_TIMESTEP in leg_conf
                    else LEGACY_CONF_TIMESTEPS[key]
                )

                config[CONF_TIMELINES] = config[CONF_TIMELINES] + [
                    {
                        CONF_NAME: None,
                        CONF_FIELDS: leg_conf[CONF_CONDITIONS],
                        CONF_FORECAST_OBSERVATIONS: leg_observations,
                        CONF_UPDATE: leg_update,
                        CONF_EXCLUDE_INTERVAL: leg_exclude,
                        CONF_SCAN_INTERVAL: leg_interval,
                        CONF_TIMESTEP: leg_timestep,
                        CONF_START_TIME: 0,
                    }
                ]
        config.pop(CONF_MONITORED_CONDITIONS)
    
    sensors = []

    for timeline_spec in config[CONF_TIMELINES]:
        timeline_spec.setdefault(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL)
        fields = timeline_spec.setdefault(CONF_FIELDS,[])
        timeline_spec.setdefault(CONF_START_TIME,0)
        observations = int(timeline_spec.get(CONF_FORECAST_OBSERVATIONS,1))
        timestep = timeline_spec.setdefault(CONF_TIMESTEP,"1d")

        if timestep == 'current':
            observations = 1
        elif not re.match('^[0-9]+[mhd]$',timestep) :
            _LOGGER.error("Invalid timestep: %s", timestep)
            continue
        
        timeline_spec[CONF_FORECAST_OBSERVATIONS]=observations

        timeline_spec.setdefault(CONF_EXCLUDE_INTERVAL,None)
        if timeline_spec[CONF_NAME] not in [None, '']:
          timeline_spec[CONF_NAME]=config.get(CONF_NAME) + timeline_spec[CONF_NAME]
        else:
          timeline_spec[CONF_NAME]=config.get(CONF_NAME)
        
        if CONF_UPDATE in timeline_spec:
            timeline_spec[CONF_UPDATE]=timeline_spec[CONF_UPDATE][0]
        else:
            timeline_spec[CONF_UPDATE]=ATTR_AUTO

        api_fields = {}

        # find API fields and detect suffixes
        for field in fields:
            suffix = ""
            suffix_name = ""
            raw = False
            if field in LEGACY_FIELDS:
                field = LEGACY_FIELDS[field]

            for suffix_option in SUFFIXES:
                if field.endswith(suffix_option):
                    field = field[: -len(suffix_option)]
                    suffix = suffix_option
                    suffix_name = " " + SUFFIXES[suffix_option]
                    break
 
            if field.startswith(RAW_PREFIX):
                raw = True
                field = field[len(RAW_PREFIX):]
                
            if field not in CLIMACELL_FIELDS:
                _LOGGER.error("Invalid field: %s", field)
                continue
            
            name = CLIMACELL_FIELDS[field][ATTR_NAME] + suffix_name
           
            unit = None
            if field in UNITS[units]:
              unit = UNITS[units][field]

            if raw and isinstance(unit, dict):
                unit = None
                name = RAW_PREFIX + " " + name

            api_fields[field + suffix] = {
                ATTR_UNIT_OF_MEASUREMENT: unit,
                ATTR_NAME: name,
                ATTR_CONDITION: CLIMACELL_FIELDS[field][ATTR_CONDITION],
                ATTR_ICON: CLIMACELL_FIELDS[field][ATTR_ICON],
            }

        timeline_spec[CONF_FIELDS]=api_fields

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
