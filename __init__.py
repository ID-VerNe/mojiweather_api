# mojiweather_api/__init__.py

# Expose key components for users
from .services import WeatherService
from .models import (
    CurrentWeather,
    DailyForecastSummary,
    LifeIndex,
    CalendarDayForecast,
    Forecast24HourItem,
    DetailedForecastDay
)
from .exceptions import (
    MojiWeatherAPIError,
    AuthenticationError,
    InvalidLocationError,
    RequestFailedError,
    ParsingError,
    HTMLStructureError,
    JSONStructureError
)
from .config import load_config, HTML_BASE_URL, JSON_BASE_URL, FORECAST10_BASE_URL, FORECAST7_BASE_URL, FORECAST15_BASE_URL, REQUEST_TIMEOUT # Expose config access
from .logger import logger # Expose logger for external use if desired

# Add a warning about the scraping component
logger.warning("请注意：包中的部分功能通过抓取墨迹天气网页实现。此方法可能不稳定，且可能违反网站的服务条款。建议优先尝试寻找官方API途径。")

# Define __all__ for explicit exports
__all__ = [
    'WeatherService', # Main service class to get data
    # Combined data fetching method
    'get_full_chained_weather_data', # Expose the new combined method
    # Individual data fetching methods (consider making internal if dependencies are strict)
    'get_full_weather_data', # Keep for main + 24h
    'get_10day_forecast_from_html', # Keep, with cautionary note in docstring

    # Data Models
    'CurrentWeather',
    'DailyForecastSummary',
    'LifeIndex',
    'CalendarDayForecast',
    'Forecast24HourItem',
    'DetailedForecastDay',
    # Exceptions
    'MojiWeatherAPIError',
    'AuthenticationError',
    'InvalidLocationError',
    'RequestFailedError',
    'ParsingError',
    'HTMLStructureError',
    'JSONStructureError',
    # Configuration Access (optional, but useful)
    'load_config', # Allow users to explicitly load config
    # 'API_KEY',
    'HTML_BASE_URL',
    'JSON_BASE_URL',
    'FORECAST10_BASE_URL', # Expose new config
    'FORECAST7_BASE_URL',
    'FORECAST15_BASE_URL',
    'REQUEST_TIMEOUT',
    'logger' # Allow users to configure logger from outside
]

# Re-export methods from WeatherService under package level for convenience
# This allows importing like 'from mojiweather_api import get_full_chained_weather_data'
# instead of 'from mojiweather_api import WeatherService' and then instantiating
# This is a common pattern for simple SDKs
_weather_service_instance = WeatherService()
get_full_weather_data = _weather_service_instance.get_full_weather_data
get_10day_forecast_from_html = _weather_service_instance.get_10day_forecast_from_html
get_full_chained_weather_data = _weather_service_instance.get_full_chained_weather_data # Export the new method