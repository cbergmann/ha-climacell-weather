import logging
import re

from custom_components.climacell.global_const import *

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

_LOGGER = logging.getLogger(__name__)

def _prepare_timeline_spec(timeline_spec, config):
    timeline_spec.setdefault(CONF_SCAN_INTERVAL,DEFAULT_SCAN_INTERVAL)
    fields = timeline_spec.setdefault(CONF_FIELDS,[])
    timeline_spec.setdefault(CONF_START_TIME,0)
    observations = int(timeline_spec.get(CONF_FORECAST_OBSERVATIONS,1))

    if timeline_spec.get(CONF_TIMESTEP,'') == 'current':
        observations = 1
    elif not re.match('^[0-9]+[mhd]$',timeline_spec.get(CONF_TIMESTEP,'')) :
        _LOGGER.error("Invalid timestep: %s, using 1d instead", timeline_spec.get(CONF_TIMESTEP,''))
        timeline_spec[CONF_TIMESTEP]="1d"
    
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
       
        unit = UNITS[config.get(CONF_UNITS)].get(field)

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

    return timeline_spec

def prepare_config(hass, config):
    _LOGGER.debug("config before prepare_config: %s.", config)
    
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

    config.setdefault(CONF_TIMELINES,[])
    
    LEGACY_CONF_TIMESTEPS = {
        CONF_REALTIME: "1m",
        CONF_DAILY: "1d",
        CONF_HOURLY: "1h",
        CONF_NOWCAST: "5m",
    }

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
    
    config[CONF_TIMELINES] = list(map(lambda tl: _prepare_timeline_spec(tl,config),config[CONF_TIMELINES]))
    _LOGGER.debug("config after prepare_config: %s.", config)
    return config


