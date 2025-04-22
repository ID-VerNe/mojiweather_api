# mojiweather_api/models.py

from typing import List, Optional
from dataclasses import dataclass, field
from .logger import logger
from .exceptions import ParsingError

@dataclass
class CurrentWeather:
    """Represents current weather conditions."""
    temperature: Optional[str] = None
    condition: Optional[str] = None
    humidity: Optional[str] = None
    wind: Optional[str] = None # e.g., "东南风3级"
    update_time: Optional[str] = None # e.g., "今天19:54更新"
    aqi: Optional[str] = None # e.g., "44 优"
    aqi_level: Optional[str] = None # e.g., "优"

@dataclass
class DailyForecastSummary:
    """Represents a daily forecast summary from the main page (Today, Tomorrow, Day after tomorrow)."""
    day_name: Optional[str] = None # e.g., "今天", "明天", "后天"
    condition: Optional[str] = None # e.g., "阵雨", "大到暴雨"
    temp_range: Optional[str] = None # e.g., "24° / 32°"
    wind: Optional[str] = None # e.g., "西南风"
    wind_level: Optional[str] = None # e.g., "3级"
    aqi: Optional[str] = None # e.g., "47 优"
    aqi_level: Optional[str] = None # e.g., "优"

@dataclass
class LifeIndex:
    """Represents a single life index item."""
    title: Optional[str] = None # e.g., "紫外线", "穿衣"
    level: Optional[str] = None # e.g., "强", "闷热"

@dataclass
class CalendarDayForecast:
    """Represents a single day's forecast from the calendar view on the main page."""
    day_of_month: Optional[str] = None # e.g., "22"
    condition: Optional[str] = None # e.g., "阵雨"
    temp_range: Optional[str] = None # e.g., "24/32°"
    wind: Optional[str] = None # e.g., "西南风  3级"
    is_active: bool = False # Whether this day is the selected/current day

@dataclass
class Forecast24HourItem:
     """Represents one hour's forecast from the 24-hour JSON data."""
     predict_date: Optional[str] = None # YYYY-MM-DD
     predict_hour: Optional[int] = None # 0-23
     temperature: Optional[int] = None # Ftemp field
     condition: Optional[str] = None # Fcondition field
     wind_speed_kph: Optional[float] = None # Fwspd field (km/h)
     wind_direction: Optional[str] = None # Fwdir field (如: SSW, S)
     wind_level: Optional[int] = None # wind_level field
     feels_like: Optional[int] = None # Ffeelslike field
     humidity: Optional[int] = None # Fhumidity field
     wind_degrees: Optional[str] = None # wind_degrees field

     @staticmethod
     def from_json(data: dict) -> 'Forecast24HourItem':
        """Creates a Forecast24HourItem from a JSON dictionary."""
        logger.debug(f"正在从JSON创建 Forecast24HourItem 实例: {data}")
        try:
            item = Forecast24HourItem(
                predict_date=data.get('Fpredict_date'),
                predict_hour=data.get('Fpredict_hour'),
                temperature=data.get('Ftemp'),
                condition=data.get('Fcondition'),
                wind_speed_kph=data.get('Fwspd'),
                wind_direction=data.get('Fwdir'),
                wind_level=data.get('wind_level'),
                feels_like=data.get('Ffeelslike'),
                humidity=data.get('Fhumidity'),
                wind_degrees=data.get('wind_degrees')
            )
            logger.debug(f"成功创建 Forecast24HourItem 实例: {item}")
            return item
        except Exception as e:
            logger.error(f"从JSON创建 Forecast24HourItem 时发生错误: {e}, 原始数据: {data}", exc_info=True)
            raise ParsingError(f"无法解析24小时预报项: {e}") from e

@dataclass
class DetailedForecastDay:
    """Represents a single day's detailed forecast from the 10-day forecast page."""
    weekday: Optional[str] = None # e.g., "周二"
    date: Optional[str] = None # e.g., "04/22"
    day_condition: Optional[str] = None # e.g., "阵雨"
    night_condition: Optional[str] = None # e.g., "阵雨"
    temp_high: Optional[str] = None # e.g., "32°"
    temp_low: Optional[str] = None # e.g., "24°"
    is_active: bool = False # Whether this day is the selected/current day