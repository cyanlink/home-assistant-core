"""Support for Buienradar.nl weather service."""

from __future__ import annotations

import logging

from buienradar.constants import (
    ATTRIBUTION,
    CONDCODE,
    CONDITION,
    DETAILED,
    EXACT,
    EXACTNL,
    FORECAST,
    IMAGE,
    MEASURED,
    PRECIPITATION_FORECAST,
    STATIONNAME,
    TIMEFRAME,
    VISIBILITY,
    WINDGUST,
    WINDSPEED,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    PERCENTAGE,
    Platform,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BuienRadarConfigEntry
from .const import (
    CONF_TIMEFRAME,
    DEFAULT_TIMEFRAME,
    STATE_CONDITION_CODES,
    STATE_CONDITIONS,
    STATE_DETAILED_CONDITIONS,
)
from .util import BrData

_LOGGER = logging.getLogger(__name__)

MEASURED_LABEL = "Measured"
TIMEFRAME_LABEL = "Timeframe"
SYMBOL = "symbol"

# Schedule next call after (minutes):
SCHEDULE_OK = 10
# When an error occurred, new call after (minutes):
SCHEDULE_NOK = 2

STATIONNAME_LABEL = "Stationname"

# icon
GAUGE_ICON = "mdi:gauge"
COMPASS_ICON = "mdi:compass-outline"
WEATHER_WINDY_ICON = "mdi:weather-windy"
WEATHER_POURING_ICON = "mdi:weather-pouring"
WEATHER_CLOUDY_ICON = "mdi:weather-partly-cloudy"

NO_FORECAST_WARNING = "No forecast for fcday=%s"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="stationname",
        translation_key="stationname",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfc",
        translation_key="barometerfc",
        icon=GAUGE_ICON,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcname",
        translation_key="barometerfcname",
        icon=GAUGE_ICON,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcnamenl",
        translation_key="barometerfcnamenl",
        icon=GAUGE_ICON,
    ),
    SensorEntityDescription(
        key="condition",
        translation_key="condition",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode",
        translation_key="conditioncode",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed",
        translation_key="conditiondetailed",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact",
        translation_key="conditionexact",
    ),
    SensorEntityDescription(
        key="symbol",
        translation_key="symbol",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="feeltemperature",
        translation_key="feeltemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="groundtemperature",
        translation_key="groundtemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windforce",
        translation_key="windforce",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="winddirection",
        translation_key="winddirection",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="windazimuth",
        translation_key="windazimuth",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        icon=GAUGE_ICON,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgust",
        translation_key="windgust",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="precipitation",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_average",
        translation_key="precipitation_forecast_average",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_total",
        translation_key="precipitation_forecast_total",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlast24hour",
        translation_key="rainlast24hour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlasthour",
        translation_key="rainlasthour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="temperature_1d",
        translation_key="temperature_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_2d",
        translation_key="temperature_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_3d",
        translation_key="temperature_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_4d",
        translation_key="temperature_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_5d",
        translation_key="temperature_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_1d",
        translation_key="mintemp_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_2d",
        translation_key="mintemp_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_3d",
        translation_key="mintemp_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_4d",
        translation_key="mintemp_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_5d",
        translation_key="mintemp_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="rain_1d",
        translation_key="rain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_2d",
        translation_key="rain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_3d",
        translation_key="rain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_4d",
        translation_key="rain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_5d",
        translation_key="rain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="minrain_1d",
        translation_key="minrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_2d",
        translation_key="minrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_3d",
        translation_key="minrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_4d",
        translation_key="minrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_5d",
        translation_key="minrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="maxrain_1d",
        translation_key="maxrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_2d",
        translation_key="maxrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_3d",
        translation_key="maxrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_4d",
        translation_key="maxrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_5d",
        translation_key="maxrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rainchance_1d",
        translation_key="rainchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_POURING_ICON,
    ),
    SensorEntityDescription(
        key="rainchance_2d",
        translation_key="rainchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_POURING_ICON,
    ),
    SensorEntityDescription(
        key="rainchance_3d",
        translation_key="rainchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_POURING_ICON,
    ),
    SensorEntityDescription(
        key="rainchance_4d",
        translation_key="rainchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_POURING_ICON,
    ),
    SensorEntityDescription(
        key="rainchance_5d",
        translation_key="rainchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_POURING_ICON,
    ),
    SensorEntityDescription(
        key="sunchance_1d",
        translation_key="sunchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_CLOUDY_ICON,
    ),
    SensorEntityDescription(
        key="sunchance_2d",
        translation_key="sunchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_CLOUDY_ICON,
    ),
    SensorEntityDescription(
        key="sunchance_3d",
        translation_key="sunchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_CLOUDY_ICON,
    ),
    SensorEntityDescription(
        key="sunchance_4d",
        translation_key="sunchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_CLOUDY_ICON,
    ),
    SensorEntityDescription(
        key="sunchance_5d",
        translation_key="sunchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=WEATHER_CLOUDY_ICON,
    ),
    SensorEntityDescription(
        key="windforce_1d",
        translation_key="windforce_1d",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="windforce_2d",
        translation_key="windforce_2d",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="windforce_3d",
        translation_key="windforce_3d",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="windforce_4d",
        translation_key="windforce_4d",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="windforce_5d",
        translation_key="windforce_5d",
        native_unit_of_measurement="Bft",
        icon=WEATHER_WINDY_ICON,
    ),
    SensorEntityDescription(
        key="windspeed_1d",
        translation_key="windspeed_1d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_2d",
        translation_key="windspeed_2d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_3d",
        translation_key="windspeed_3d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_4d",
        translation_key="windspeed_4d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_5d",
        translation_key="windspeed_5d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="winddirection_1d",
        translation_key="winddirection_1d",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="winddirection_2d",
        translation_key="winddirection_2d",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="winddirection_3d",
        translation_key="winddirection_3d",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="winddirection_4d",
        translation_key="winddirection_4d",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="winddirection_5d",
        translation_key="winddirection_5d",
        icon=COMPASS_ICON,
    ),
    SensorEntityDescription(
        key="windazimuth_1d",
        translation_key="windazimuth_1d",
        native_unit_of_measurement=DEGREE,
        icon=COMPASS_ICON,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_2d",
        translation_key="windazimuth_2d",
        native_unit_of_measurement=DEGREE,
        icon=COMPASS_ICON,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_3d",
        translation_key="windazimuth_3d",
        native_unit_of_measurement=DEGREE,
        icon=COMPASS_ICON,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_4d",
        translation_key="windazimuth_4d",
        native_unit_of_measurement=DEGREE,
        icon=COMPASS_ICON,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_5d",
        translation_key="windazimuth_5d",
        native_unit_of_measurement=DEGREE,
        icon=COMPASS_ICON,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="condition_1d",
        translation_key="condition_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_2d",
        translation_key="condition_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_3d",
        translation_key="condition_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_4d",
        translation_key="condition_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_5d",
        translation_key="condition_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode_1d",
        translation_key="conditioncode_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_2d",
        translation_key="conditioncode_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_3d",
        translation_key="conditioncode_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_4d",
        translation_key="conditioncode_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_5d",
        translation_key="conditioncode_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed_1d",
        translation_key="conditiondetailed_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_2d",
        translation_key="conditiondetailed_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_3d",
        translation_key="conditiondetailed_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_4d",
        translation_key="conditiondetailed_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_5d",
        translation_key="conditiondetailed_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact_1d",
        translation_key="conditionexact_1d",
    ),
    SensorEntityDescription(
        key="conditionexact_2d",
        translation_key="conditionexact_2d",
    ),
    SensorEntityDescription(
        key="conditionexact_3d",
        translation_key="conditionexact_3d",
    ),
    SensorEntityDescription(
        key="conditionexact_4d",
        translation_key="conditionexact_4d",
    ),
    SensorEntityDescription(
        key="conditionexact_5d",
        translation_key="conditionexact_5d",
    ),
    SensorEntityDescription(
        key="symbol_1d",
        translation_key="symbol_1d",
    ),
    SensorEntityDescription(
        key="symbol_2d",
        translation_key="symbol_2d",
    ),
    SensorEntityDescription(
        key="symbol_3d",
        translation_key="symbol_3d",
    ),
    SensorEntityDescription(
        key="symbol_4d",
        translation_key="symbol_4d",
    ),
    SensorEntityDescription(
        key="symbol_5d",
        translation_key="symbol_5d",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuienRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the buienradar sensor."""
    config = entry.data
    options = entry.options

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    timeframe = options.get(
        CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
    )

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    _LOGGER.debug(
        "Initializing buienradar sensor coordinate %s, timeframe %s",
        coordinates,
        timeframe,
    )

    # create weather entities:
    entities = [
        BrSensor(config.get(CONF_NAME, "Buienradar"), coordinates, description)
        for description in SENSOR_TYPES
    ]

    # create weather data:
    data = BrData(hass, coordinates, timeframe, entities)
    entry.runtime_data[Platform.SENSOR] = data
    await data.async_update()

    async_add_entities(entities)


class BrSensor(SensorEntity):
    """Representation of a Buienradar sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, client_name, coordinates, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._data: BrData | None = None
        self._measured = None
        self._attr_unique_id = (
            f"{coordinates[CONF_LATITUDE]:2.6f}{coordinates[CONF_LONGITUDE]:2.6f}"
            f"{description.key}"
        )

        # All continuous sensors should be forced to be updated
        self._attr_force_update = (
            description.key != SYMBOL and not description.key.startswith(CONDITION)
        )

        if description.key.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        if self._data is None:
            return
        self._update()

    @callback
    def data_updated(self, data: BrData):
        """Handle data update."""
        self._data = data
        if not self.hass:
            return
        self._update()

    def _update(self):
        """Update sensor data."""
        _LOGGER.debug("Updating sensor %s", self.entity_id)
        if self._load_data(self._data.data):
            self.async_write_ha_state()

    @callback
    def _load_data(self, data):  # noqa: C901
        """Load the sensor with relevant data."""
        # Check if we have a new measurement,
        # otherwise we do not have to update the sensor
        if self._measured == data.get(MEASURED):
            return False

        self._measured = data.get(MEASURED)
        sensor_type = self.entity_description.key

        if sensor_type.endswith(("_1d", "_2d", "_3d", "_4d", "_5d")):
            return self._handle_forecast_sensor(data, sensor_type)

        if sensor_type == SYMBOL or sensor_type.startswith(CONDITION):
            return self._update_condition_sensor(data, sensor_type)

        if sensor_type.startswith(PRECIPITATION_FORECAST):
            return self._update_precipitation_forecast(data, sensor_type)

        if sensor_type in [WINDSPEED, WINDGUST]:
            return self._update_windspeed_sensor(data, sensor_type)

        if sensor_type == VISIBILITY:
            return self._update_visibility_sensor(data, sensor_type)
        
        # update all other sensors
        return self._update_standard_sensor(data, sensor_type)
    

    def _handle_forecast_sensor(self, data, sensor_type: str) -> bool:
        # update forecasting sensors:
        # get fcday
        fcday = self._get_forecast_day(sensor_type)

        # update weather symbol & status text
        if sensor_type.startswith((SYMBOL, CONDITION)):
            return self._update_forecast_condition(data, fcday, sensor_type)

        if sensor_type.startswith(WINDSPEED):
            return self._update_forecast_windspeed(data, fcday, sensor_type)

        # update all other sensors
        return self._update_forecast_standard(data, fcday, sensor_type)

    def _get_forecast_day(self, sensor_type: str) -> int:
        """Get forecast day from sensor type suffix."""
        suffix_to_day = {"_1d": 0, "_2d": 1, "_3d": 2, "_4d": 3, "_5d": 4}
        for suffix, day in suffix_to_day.items():
            if sensor_type.endswith(suffix):
                return day
        return 0

    def _update_forecast_condition(self, data, fcday: int, sensor_type: str) -> bool:
        try:
            condition = data.get(FORECAST)[fcday].get(CONDITION)
        except IndexError:
            _LOGGER.warning(NO_FORECAST_WARNING, fcday)
            return False

        if condition:
            # Map sensor type to condition field
            type_to_field = {
                SYMBOL: EXACTNL,
                CONDITION: CONDITION,
                "conditioncode": CONDCODE,
                "conditiondetailed": DETAILED,
                "conditionexact": EXACT,
            }
        
            field = None
            for prefix, field_name in type_to_field.items():
                if sensor_type.startswith(prefix):
                    field = field_name
                    break
        
            if field:
                new_state = condition.get(field)
                img = condition.get(IMAGE)

                if new_state != self.state or img != self.entity_picture:
                    self._attr_native_value = new_state
                    self._attr_entity_picture = img
                    return True
    
        return False

    def _update_forecast_windspeed(self, data, fcday: int, sensor_type: str) -> bool:
        # hass wants windspeeds in km/h not m/s, so convert:
        try:
            self._attr_native_value = data.get(FORECAST)[fcday].get(
                sensor_type[:-3]
            )
        except IndexError:
            _LOGGER.warning(NO_FORECAST_WARNING, fcday)
            return False

        if self.state is not None:
            self._attr_native_value = round(self.state * 3.6, 1)
        return True

    def _update_forecast_standard(self, data, fcday: int, sensor_type: str) -> bool:
        # update all other sensors
        try:
            self._attr_native_value = data.get(FORECAST)[fcday].get(
                sensor_type[:-3]
            )
        except IndexError:
            _LOGGER.warning(NO_FORECAST_WARNING, fcday)
            return False
        return True

    def _update_condition_sensor(self, data, sensor_type: str) -> bool:
        # update weather symbol & status text
        if condition := data.get(CONDITION):
            # Map sensor type to condition field
            type_to_field = {
                SYMBOL: EXACTNL,
                CONDITION: CONDITION,
                "conditioncode": CONDCODE,
                "conditiondetailed": DETAILED,
                "conditionexact": EXACT,
            }

            field = type_to_field.get(sensor_type)

            if field:
                new_state = condition.get(field)
                img = condition.get(IMAGE)

                if new_state != self.state or img != self.entity_picture:
                    self._attr_native_value = new_state
                    self._attr_entity_picture = img
                    return True

        return False

    def _update_precipitation_forecast(self, data, sensor_type: str) -> bool:
        # update nested precipitation forecast sensors
        nested = data.get(PRECIPITATION_FORECAST)
        self._timeframe = nested.get(TIMEFRAME)
        self._attr_native_value = nested.get(
            sensor_type[len(PRECIPITATION_FORECAST) + 1 :]
        )
        return True

    def _update_windspeed_sensor(self, data, sensor_type: str) -> bool:
        # hass wants windspeeds in km/h not m/s, so convert:
        self._attr_native_value = data.get(sensor_type)
        if self.state is not None:
            self._attr_native_value = round(data.get(sensor_type) * 3.6, 1)
        return True
    
    def _update_visibility_sensor(self, data, sensor_type: str) -> bool:
        # hass wants visibility in km (not m), so convert:
        self._attr_native_value = data.get(sensor_type)
        if self.state is not None:
            self._attr_native_value = round(self.state / 1000, 1)
        return True

    def _update_standard_sensor(self, data, sensor_type: str) -> bool:
        self._attr_native_value = data.get(sensor_type)
        if sensor_type.startswith(PRECIPITATION_FORECAST):
            result = {ATTR_ATTRIBUTION: data.get(ATTRIBUTION)}
            if self._timeframe is not None:
                result[TIMEFRAME_LABEL] = f"{self._timeframe} min"

            self._attr_extra_state_attributes = result

        result = {
            ATTR_ATTRIBUTION: data.get(ATTRIBUTION),
            STATIONNAME_LABEL: data.get(STATIONNAME),
        }
        if self._measured is not None:
            # convert datetime (Europe/Amsterdam) into local datetime
            local_dt = dt_util.as_local(self._measured)
            result[MEASURED_LABEL] = local_dt.strftime("%c")

        self._attr_extra_state_attributes = result
        return True