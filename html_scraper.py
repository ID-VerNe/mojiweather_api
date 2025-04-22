# mojiweather_api/html_scraper.py

import httpx
from bs4 import BeautifulSoup
from typing import Dict, Any, Optional, List, Tuple
from .logger import logger
from .exceptions import RequestFailedError, HTMLStructureError, ParsingError, InvalidLocationError, MojiWeatherAPIError
from .models import CurrentWeather, DailyForecastSummary, LifeIndex, CalendarDayForecast, DetailedForecastDay
from .config import HTML_BASE_URL, FORECAST10_BASE_URL, REQUEST_TIMEOUT, \
    FORECAST7_BASE_URL, FORECAST15_BASE_URL  # Import base URLs and timeout from config

class MojiWeatherHTMLScraper:
    """Scrapes weather data from Moji Weather HTML pages."""

    def __init__(self):
        logger.info("初始化 MojiWeatherHTMLScraper")
        pass

    async def fetch_html_page(self, url: str, client: httpx.AsyncClient, referer: Optional[str] = None) -> httpx.Response:
        """
        Fetches an HTML page.

        Args:
            url: The URL to fetch.
            client: An httpx.AsyncClient instance.
            referer: The Referer header value.

        Returns:
            The httpx.Response object.

        Raises:
            RequestFailedError: If the HTTP request fails.
        """
        logger.info(f"正在获取 HTML 页面: {url}")

        standard_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,it;q=0.7,ko;q=0.6",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
             "DNT": "1",
             "Sec-GPC": "1"
            # Cookies handled by client implicitly due to AsyncClient instance reuse.
            # Sec-Fetch-Site is omitted here as it depends on navigation context (same-origin, cross-site, etc.)
        }
        if referer:
            standard_headers["Referer"] = referer
            logger.debug(f"设置 Referer: {referer}")
        else:
             logger.debug("未设置 Referer")

        logger.debug(f"发送 HTML 请求头: {standard_headers}")

        try:
            response = await client.get(url, headers=standard_headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status() # Raises HTTPStatusError for bad responses (4xx or 5xx)
            logger.info(f"成功获取页面: 请求 URL={url}, 最终 URL={response.url}, Status Code={response.status_code}")
            logger.debug(f"接收到 HTML 响应头: {response.headers}")
            return response

        except httpx.RequestError as e:
             if isinstance(e, httpx.ConnectTimeout) or isinstance(e, httpx.ReadTimeout):
                 logger.error(f"获取页面超时: URL={url}, 错误: {e}", exc_info=True)
                 raise RequestFailedError(f"获取天气页面超时: {e}") from e
             elif isinstance(e, httpx.HTTPStatusError):
                logger.error(f"获取页面失败 (HTTP 状态码错误): URL={url}, Status: {e.response.status_code}, 响应内容长度: {len(e.response.content) if e.response is not None else 0}, 错误详情: {e}", exc_info=True)
                # Check if it's a 404 or similar, might indicate invalid slug
                if e.response.status_code == 404:
                     logger.warning(f"获取页面返回 404 Not Found: URL={url}")
                     raise InvalidLocationError(f"未找到该城市的天气页面: {url}") from e

             else:
                 logger.error(f"获取页面失败 (请求错误): URL={url}, 错误类型: {type(e).__name__}, 错误详情: {e}", exc_info=True)
             raise RequestFailedError(f"获取天气页面失败: {e}") from e
        except Exception as e:
             logger.error(f"获取页面时发生未知错误: URL={url}, 错误类型: {type(e).__name__}, 错误详情: {e}", exc_info=True)
             raise RequestFailedError(f"获取天气页面时发生未知错误: {e}") from e

    async def fetch_and_parse_weather_page(self, city_slug: str, client: httpx.AsyncClient) -> Tuple[Dict[str, Any], str]:
        """
        Fetches the main HTML page for a given city slug and parses key weather data.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").
            client: An httpx.AsyncClient instance to use for the request.

        Returns:
            A tuple containing:
            - A dictionary of parsed weather data components (current, daily_summary, life_indices, calendar).
              Value is None for any section that could not be parsed successfully.
            - The actual URL of the fetched HTML page (useful for setting Referer).

        Raises:
            RequestFailedError: If the HTTP request fails.
            InvalidLocationError: If the city slug results in a 404.
            HTMLStructureError: If parsing of critical sections fails critically.
        """
        logger.info(f"正在抓取并解析城市主天气页面: city_slug={city_slug}")
        url = f"{HTML_BASE_URL}/{city_slug}"
        logger.debug(f"目标 URL: {url}")

        try:
            response = await self.fetch_html_page(url, client, referer=HTML_BASE_URL) # Use base URL as referer for the initial request
            soup = BeautifulSoup(response.content, 'html.parser')
            actual_url = str(response.url) # Get the final URL after any redirects
            logger.debug(f"主天气页面 HTML 解析完成 from {actual_url}, 开始提取数据...")

            parsed_data = {
                "current": self._parse_current_weather(soup),
                "daily_summary": self._parse_daily_forecast_summary(soup),
                "life_indices": self._parse_life_indices(soup),
                "calendar": self._parse_calendar_forecast(soup),
                # Add other parsing methods here as needed
            }

            # Check for critical missing data after parsing
            if not parsed_data.get("current") and not parsed_data.get("daily_summary"):
                 logger.error(f"未能从主天气页面解析出当前天气和每日预报摘要数据。HTML结构可能已严重改变。city_slug={city_slug}, URL={actual_url}")
                 # Decide whether to raise a critical error here. If main page fails, subsequent requests reliant on cookies might also fail.
                 raise HTMLStructureError(f"未能从主天气页面解析出核心天气数据 from {actual_url}. HTML结构可能已严重改变。")

            if not any(parsed_data.values()):
                 logger.warning(f"主天气页面解析完成，但未能提取任何字段的有效数据: {actual_url}")

            logger.info(f"主天气页面解析完成 from {actual_url}, 提取到 {sum(1 for v in parsed_data.values() if v is not None)} 部分数据")

            return parsed_data, actual_url

        except (RequestFailedError, InvalidLocationError, HTMLStructureError) as e:
            # Re-raise known request or critical parsing errors
            raise e
        except Exception as e:
            logger.error(f"解析城市主天气页面时发生不可预测错误: {e}", exc_info=True)
            raise ParsingError(f"解析城市主天气页面时发生不可预测错误: {e}") from e

    async def fetch_and_parse_10day_forecast(self, city_slug: str, client: httpx.AsyncClient, referer_url: str) -> Optional[List[DetailedForecastDay]]:
        """
        Fetches the 10-day forecast page and parses the forecast list.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").
            client: An httpx.AsyncClient instance.
            referer_url: The URL of the immediately preceding page request (e.g., the main weather page or 24h JSON?).

        Returns:
            A list of DetailedForecastDay objects, or None if parsing fails critically.

        Raises:
            RequestFailedError: If fetching the HTML page fails.
            InvalidLocationError: If the city slug results in a 404.
            HTMLStructureError: If parsing the 10-day forecast list fails critically (e.g., unable to find list container).
            ParsingError: For other parsing issues within the list.
        """
        logger.info(f"正在抓取并解析 10天预报页面: city_slug={city_slug}")
        # Use the configured FORECAST10_BASE_URL
        url = f"{FORECAST10_BASE_URL}/{city_slug}"
        logger.debug(f"目标 URL: {url}")

        try:
            # Use the provided referer_url (presumably from the previous successful request)
            response = await self.fetch_html_page(url, client, referer=referer_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            actual_url = str(response.url)
            logger.debug(f"10天预报页面 HTML 解析完成 from {actual_url}, 开始提取数据...")

            forecast_list = self._parse_10day_forecast(soup)

            if not forecast_list:
                logger.warning(f"未能从 10天预报页面解析出任何有效的预报项。HTML结构可能已改变。URL={actual_url}")
                # If no items were parsed, it's a critical parsing error for this section
                raise HTMLStructureError(f"未能从 10天预报页面解析出任何有效预报项 from {actual_url}. HTML结构可能已改变。")

            logger.info(f"成功从 10天预报页面解析出 {len(forecast_list)} 个预报项 from {actual_url}")
            return forecast_list

        except (RequestFailedError, InvalidLocationError) as e:
            # Re-raise network or 404 errors from fetch_html_page
             logger.error(f"获取 10天预报页面失败: URL={url}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
             raise
        except HTMLStructureError as e: # Catch parsing issues from _parse_10day_forecast
             # Error already logged in _parse_10day_forecast if container is missing
             raise # Re-raise the specific parsing error
        except ParsingError as e: # Catch other parsing issues within the list
             logger.error(f"解析 10天预报数据时发生可预测错误: URL={url}, 错误: {e}", exc_info=True)
             raise # Re-raise the specific parsing error
        except Exception as e:
              logger.error(f"抓取或解析 10天预报页面时发生不可预测错误: URL={url}, 错误: {e}", exc_info=True)
              raise MojiWeatherAPIError(f"抓取或解析 10天预报页面时发生不可预测错误: {e}") from e

    async def fetch_and_parse_15day_forecast(self, city_slug: str, client: httpx.AsyncClient, referer_url: str) -> Optional[List[DetailedForecastDay]]:
        """
        Fetches the 15-day forecast page and parses the forecast list.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").
            client: An httpx.AsyncClient instance.
            referer_url: The URL of the immediately preceding page request (e.g., the main weather page or 24h JSON?).

        Returns:
            A list of DetailedForecastDay objects, or None if parsing fails critically.

        Raises:
            RequestFailedError: If fetching the HTML page fails.
            InvalidLocationError: If the city slug results in a 404.
            HTMLStructureError: If parsing the 15-day forecast list fails critically (e.g., unable to find list container).
            ParsingError: For other parsing issues within the list.
        """
        logger.info(f"正在抓取并解析 15天预报页面: city_slug={city_slug}")
        # Use the configured FORECAST15_BASE_URL
        url = f"{FORECAST15_BASE_URL}/{city_slug}"
        logger.debug(f"目标 URL: {url}")

        try:
            # Use the provided referer_url (presumably from the previous successful request)
            response = await self.fetch_html_page(url, client, referer=referer_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            actual_url = str(response.url)
            logger.debug(f"15天预报页面 HTML 解析完成 from {actual_url}, 开始提取数据...")

            forecast_list = self._parse_15day_forecast(soup)

            if not forecast_list:
                logger.warning(f"未能从 15天预报页面解析出任何有效的预报项。HTML结构可能已改变。URL={actual_url}")
                # If no items were parsed, it's a critical parsing error for this section
                raise HTMLStructureError(f"未能从 15天预报页面解析出任何有效预报项 from {actual_url}. HTML结构可能已改变。")

            logger.info(f"成功从 15天预报页面解析出 {len(forecast_list)} 个预报项 from {actual_url}")
            return forecast_list

        except (RequestFailedError, InvalidLocationError) as e:
            # Re-raise network or 404 errors from fetch_html_page
             logger.error(f"获取 15天预报页面失败: URL={url}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
             raise
        except HTMLStructureError as e: # Catch parsing issues from _parse_15day_forecast
             # Error already logged in _parse_15day_forecast if container is missing
             raise # Re-raise the specific parsing error
        except ParsingError as e: # Catch other parsing issues within the list
             logger.error(f"解析 15天预报数据时发生可预测错误: URL={url}, 错误: {e}", exc_info=True)
             raise # Re-raise the specific parsing error
        except Exception as e:
              logger.error(f"抓取或解析 15天预报页面时发生不可预测错误: URL={url}, 错误: {e}", exc_info=True)
              raise MojiWeatherAPIError(f"抓取或解析 15天预报页面时发生不可预测错误: {e}") from e

    async def fetch_and_parse_7day_forecast(self, city_slug: str, client: httpx.AsyncClient, referer_url: str) -> Optional[List[DetailedForecastDay]]:
        """
        Fetches the 7-day forecast page and parses the forecast list.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").
            client: An httpx.AsyncClient instance.
            referer_url: The URL of the immediately preceding page request (e.g., the main weather page or 24h JSON?).

        Returns:
            A list of DetailedForecastDay objects, or None if parsing fails critically.

        Raises:
            RequestFailedError: If fetching the HTML page fails.
            InvalidLocationError: If the city slug results in a 404.
            HTMLStructureError: If parsing the 7-day forecast list fails critically (e.g., unable to find list container).
            ParsingError: For other parsing issues within the list.
        """
        logger.info(f"正在抓取并解析 7天预报页面: city_slug={city_slug}")
        # Use the configured FORECAST7_BASE_URL
        url = f"{FORECAST7_BASE_URL}/{city_slug}"
        logger.debug(f"目标 URL: {url}")

        try:
            # Use the provided referer_url (presumably from the previous successful request)
            response = await self.fetch_html_page(url, client, referer=referer_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            actual_url = str(response.url)
            logger.debug(f"7天预报页面 HTML 解析完成 from {actual_url}, 开始提取数据...")

            forecast_list = self._parse_7day_forecast(soup)

            if not forecast_list:
                logger.warning(f"未能从 7天预报页面解析出任何有效的预报项。HTML结构可能已改变。URL={actual_url}")
                # If no items were parsed, it's a critical parsing error for this section
                raise HTMLStructureError(f"未能从 7天预报页面解析出任何有效预报项 from {actual_url}. HTML结构可能已改变。")

            logger.info(f"成功从 7天预报页面解析出 {len(forecast_list)} 个预报项 from {actual_url}")
            return forecast_list

        except (RequestFailedError, InvalidLocationError) as e:
            # Re-raise network or 404 errors from fetch_html_page
             logger.error(f"获取 7天预报页面失败: URL={url}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
             raise
        except HTMLStructureError as e: # Catch parsing issues from _parse_7day_forecast
             # Error already logged in _parse_7day_forecast if container is missing
             raise # Re-raise the specific parsing error
        except ParsingError as e: # Catch other parsing issues within the list
             logger.error(f"解析 7天预报数据时发生可预测错误: URL={url}, 错误: {e}", exc_info=True)
             raise # Re-raise the specific parsing error
        except Exception as e:
              logger.error(f"抓取或解析 7天预报页面时发生不可预测错误: URL={url}, 错误: {e}", exc_info=True)
              raise MojiWeatherAPIError(f"抓取或解析 7天预报页面时发生不可预测错误: {e}") from e


    # Keep the parsing methods unchanged from the previous version
    # _parse_current_weather, _parse_daily_forecast_summary, _parse_life_indices, _parse_calendar_forecast, _parse_10day_forecast

    # ... paste _parse_current_weather
    def _parse_current_weather(self, soup: BeautifulSoup) -> Optional[CurrentWeather]:
        """Parses current weather data from the soup object."""
        logger.debug("正在解析当前天气数据...")
        try:
            # Selectors based on the provided HTML structure.
            temp_elem = soup.select_one('.wea_weather em')
            condition_elem = soup.select_one('.wea_weather b')
            update_time_elem = soup.select_one('.wea_weather strong.info_uptime')
            about_elems = soup.select('.wea_about span, .wea_about em')
            # AQI is in the first list item of .wea_alert ul
            aqi_container = soup.select_one('.wea_alert ul li:nth-child(1) a')
            aqi_elem = aqi_container.select_one('span.level strong') if aqi_container else None

            # Handle case where main weather details might be in a different structure on forecast pages
            # Check if the section exists first
            main_weather_section = soup.select_one('.wea_weather')
            if not main_weather_section:
                 # Check alternative structure found in 10day forecast page HTML
                 detail_weather_section = soup.select_one('#detail_info .detail_weather')
                 if detail_weather_section:
                      logger.debug("解析主页面当前天气数据，使用 detail_weather 结构.")
                      # The 10 day page shows range, not current temp directly in this section.
                      logger.warning("10天预报页面结构显示的是 temperature range, 不是实时温度. 此 section 无效用于获取当前天气。")
                      return None

                 logger.warning("未能找到当前天气数据容器 (.wea_weather 或 #detail_info .detail_weather_section).")
                 return None

            temperature = temp_elem.get_text(strip=True) if temp_elem else None
            condition = condition_elem.get_text(strip=True) if condition_elem else None
            update_time = update_time_elem.get_text(strip=True) if update_time_elem else None

            humidity = None
            wind = None
            # Ensure about_elems has enough items before accessing them
            if len(about_elems) > 0:
                 humidity_text = about_elems[0].get_text(strip=True) if about_elems[0] else None
                 # Check if the text looks like humidity before assigning
                 if humidity_text and '湿度' in humidity_text:
                      humidity = humidity_text
                 else:
                      logger.debug(f"Found first .wea_about item but it does not look like humidity: {humidity_text}")

            if len(about_elems) > 1:
                 wind_text = about_elems[1].get_text(strip=True) if about_elems[1] else None
                 # Check if the text looks like wind before assigning
                 if wind_text and ('风' in wind_text or '级' in wind_text):
                      wind = wind_text
                 else:
                      logger.debug(f"Found second .wea_about item but it does not look like wind: {wind_text}")

            aqi_full = aqi_elem.get_text(strip=True) if aqi_elem else None
            aqi_level = None
            if aqi_full and ' ' in aqi_full:
                 aqi_parts = aqi_full.split(' ')
                 if len(aqi_parts) > 1:
                    aqi_level = aqi_parts[-1]
                 else:
                    aqi_level = aqi_full

            current_weather = CurrentWeather(
                temperature=temperature,
                condition=condition,
                humidity=humidity,
                wind=wind,
                update_time=update_time,
                aqi=aqi_full,
                aqi_level=aqi_level
            )

            # Log WARNING if crucial data fields are None
            if not current_weather.temperature: logger.warning("当前天气解析: 未找到温度或为 None")
            if not current_weather.condition: logger.warning("当前天气解析: 未找到天气状况或为 None")
            if not current_weather.update_time: logger.warning("当前天气解析: 未找到更新时间或为 None")
            if not current_weather.humidity: logger.warning("当前天气解析: 未找到湿度或为 None")
            if not current_weather.wind: logger.warning("当前天气解析: 未找到风力风向或为 None")
            if not current_weather.aqi: logger.warning("当前天气解析: 未找到AQI或为 None")

            logger.debug(f"当前天气解析结果: {current_weather}")

            # Decide if parsing is considered successful for this section
            # If at least temperature and condition are found, consider it partially successful.
            if not any([current_weather.temperature, current_weather.condition]):
                 logger.warning("未能解析出当前天气最核心数据 (温度或状况)，此 section 无效。")
                 # If none of the fields were found, treat as not found
                 if not any([current_weather.update_time, current_weather.humidity, current_weather.wind, current_weather.aqi]):
                     logger.warning("当前天气数据 section 未找到或结构异常。")
                     return None
                 # If some auxiliary data was found, return the incomplete object
                 return current_weather

            return current_weather

        except Exception as e:
            logger.error(f"解析当前天气数据时发生不可预测错误: {e}", exc_info=True)
            return None

    # ... paste _parse_daily_forecast_summary
    def _parse_daily_forecast_summary(self, soup: BeautifulSoup) -> List[DailyForecastSummary]:
        """Parses daily forecast summaries (Today, Tomorrow, Day after tomorrow) from the soup object."""
        logger.debug("正在解析每日预报摘要 (主页面)...")
        forecast_list = []
        try:
            # Select the first few '.days' lists under '.forecast' which contain the summary
            daily_forecast_elements = soup.select('.forecast > ul.days')

            # Expecting at least 3 such ULs for core summary
            if len(daily_forecast_elements) < 3:
                 logger.warning(f"找到的每日预报摘要 UL 元素少于3个 ({len(daily_forecast_elements)} found). HTML结构可能已改变。")
                 if not daily_forecast_elements: return None

            logger.debug(f"找到 {len(daily_forecast_elements)} 个每日预报 UL 元素")

            # Iterate through the first few, assuming their structure
            for i, day_elem in enumerate(daily_forecast_elements):
                try:
                    # Extract Day Name
                    day_name_elem = day_elem.select_one('li:nth-child(1) a, li:nth-child(1) span')
                    day_name = day_name_elem.get_text(strip=True) if day_name_elem else f"第{i+1}天"

                    # Extract Condition Text
                    condition_li_elem = day_elem.select_one('li:nth-child(2)')
                    condition = None
                    if condition_li_elem:
                         condition_text_parts = [text.strip() for text in condition_li_elem.contents if isinstance(text, str) and text.strip()]
                         condition = " ".join(condition_text_parts) if condition_text_parts else "未知状况"
                         if condition == "未知状况": # Fallback to alt text
                              img_alt_elem = condition_li_elem.select_one('img')
                              if img_alt_elem and img_alt_elem.get('alt'):
                                   condition = img_alt_elem.get('alt').strip()

                    # Extract Temperature Range
                    temp_range_elem = day_elem.select_one('li:nth-child(3)')
                    temp_range = temp_range_elem.get_text(strip=True) if temp_range_elem else None

                    # Extract Wind and Wind Level
                    wind_elem = day_elem.select_one('li:nth-child(4) em')
                    wind_level_elem = day_elem.select_one('li:nth-child(4) b')
                    wind = wind_elem.get_text(strip=True) if wind_elem else None
                    wind_level = wind_level_elem.get_text(strip=True) if wind_level_elem else None

                    # Extract AQI
                    aqi_elem = day_elem.select_one('li:nth-child(5) strong')
                    aqi_full = aqi_elem.get_text(strip=True) if aqi_elem else None
                    aqi_level = None
                    if aqi_full and ' ' in aqi_full:
                         aqi_parts = aqi_full.split(' ')
                         if len(aqi_parts) > 1:
                              aqi_level = aqi_parts[-1]
                         else:
                              aqi_level = aqi_full

                    if day_name and condition != "未知状况" and temp_range:
                         forecast = DailyForecastSummary(
                             day_name=day_name,
                             condition=condition,
                             temp_range=temp_range,
                             wind=wind,
                             wind_level=wind_level,
                             aqi=aqi_full,
                             aqi_level=aqi_level
                         )
                         forecast_list.append(forecast)
                         # logger.debug(f"解析到每日预报摘要项: {forecast}") # Avoid spamming debug logs
                    else:
                         logger.warning(f"跳过不完整的每日预报摘要项 (索引 {i}): Day='{day_name}', Condition='{condition}', Temp='{temp_range}'")

                except Exception as e:
                     logger.error(f"解析每日预报摘要项 (索引 {i}) 时发生错误: {e}", exc_info=True)

            logger.debug(f"共解析到 {len(forecast_list)} 个每日预报摘要项")
            return forecast_list if forecast_list else None

        except Exception as e:
            logger.error(f"解析每日预报摘要时发生不可预测错误: {e}", exc_info=True)
            return None

    # ... paste _parse_life_indices
    def _parse_life_indices(self, soup: BeautifulSoup) -> Optional[List[LifeIndex]]:
        """Parses life index data from the soup object."""
        logger.debug("正在解析生活指数...")
        index_list = []
        try:
            # Select all list items within the live_index_grid ul
            index_items = soup.select('#live_index .live_index_grid ul li')
            logger.debug(f"找到 {len(index_items)} 个生活指数元素容器")

            if not index_items:
                 logger.warning("未能找到生活指数元素容器，HTML结构可能已改变。")
                 return None

            for i, item_elem in enumerate(index_items):
                try:
                    link_elem = item_elem.select_one('a')
                    if link_elem:
                        level_elem = link_elem.select_one('dl dt')
                        title_elem = link_elem.select_one('dl dd')

                        level = level_elem.get_text(strip=True) if level_elem else None
                        title = title_elem.get_text(strip=True) if title_elem else None

                        if level and title:
                            index = LifeIndex(title=title, level=level)
                            index_list.append(index)
                            # logger.debug(f"解析到生活指数项 (索引 {i}): {index}") # Avoid spamming debug logs
                        else:
                             logger.warning(f"跳过不完整的生活指数项 (索引 {i}): Level='{level}', Title='{title}'")
                    else:
                         logger.debug(f"跳过非生活指数链接元素或结构不匹配 (索引 {i})")

                except Exception as e:
                    logger.error(f"解析单个生活指数项 (索引 {i}) 时发生错误: {e}", exc_info=True)
                    # Continue to next item on error

            logger.debug(f"共解析到 {len(index_list)} 个生活指数项")
            # Return None if list is empty even though container was found - indicates parsing issue
            return index_list if index_list else None

        except Exception as e:
            logger.error(f"解析生活指数时发生不可预测错误: {e}", exc_info=True)
            return None

    def _parse_calendar_forecast(self, soup: BeautifulSoup) -> Optional[List[CalendarDayForecast]]:
        """Parses calendar forecast data from the main page soup object."""
        # Note: This method is for the calendar view on the main page, not the 10-day list page.
        logger.debug("正在解析天气日历 (主页面)...")
        calendar_list = []
        try:
            day_items = soup.select('#calendar_grid ul li.item em')
            day_item_containers = [item.parent for item in day_items if item.parent]

            logger.debug(f"找到 {len(day_item_containers)} 个天气日历元素")

            if not day_item_containers:
                 logger.warning("未能找到天气日历元素容器，HTML结构可能已改变。")
                 return None

            for i, item_elem in enumerate(day_item_containers):
                try:
                    day_number_elem = item_elem.select_one('em')
                    condition_img_alt = item_elem.select_one('b img')
                    temp_range_elem = item_elem.select_one('p:nth-of-type(1)')
                    wind_elem = item_elem.select_one('p:nth-of-type(2)')
                    is_active = 'active' in item_elem.get('class', [])

                    day_number = day_number_elem.get_text(strip=True) if day_number_elem else None
                    condition = condition_img_alt.get('alt').strip() if condition_img_alt and condition_img_alt.get('alt') else "未知状况"
                    temp_range = temp_range_elem.get_text(strip=True) if temp_range_elem else None
                    wind = wind_elem.get_text(strip=True).replace('\u00a0', ' ') if wind_elem else None

                    if day_number and condition != "未知状况":
                        calendar_day = CalendarDayForecast(
                            day_of_month=day_number,
                            condition=condition,
                            temp_range=temp_range,
                            wind=wind,
                            is_active=is_active
                        )
                        calendar_list.append(calendar_day)
                        # logger.debug(f"解析到天气日历项 (索引 {i}): 日 {day_number}, 状况 {condition}") # Avoid spamming
                    else:
                         logger.warning(f"跳过不完整或无效的天气日历项 (索引 {i}, 天数: '{day_number}', 状况: '{condition}')")

                except Exception as e:
                    logger.error(f"解析单个天气日历项 (索引 {i})时发生错误: {e}", exc_info=True)

            logger.debug(f"共解析到 {len(calendar_list)} 个天气日历项")
            # Return None if list is empty even though container was found - indicates parsing issue
            return calendar_list if calendar_list else None

        except Exception as e:
            logger.error(f"解析天气日历时发生不可预测错误: {e}", exc_info=True)
            return None

    def _parse_10day_forecast(self, soup: BeautifulSoup) -> Optional[List[DetailedForecastDay]]:
        """
        Parses the 10-day forecast list from the #detail_future section.
        """
        logger.debug("正在解析 10天预报列表...")
        forecast_list = []
        try:
            # Select the container for the 10-day forecast items
            forecast_list_container = soup.select_one('#detail_future .detail_future_grid .wea_list ul')
            if not forecast_list_container:
                logger.warning("未能找到 10天预报列表容器 (#detail_future .detail_future_grid .wea_list ul)，HTML结构可能已改变。")
                return None # Return None if the main container is not found

            # Select individual list items within the container
            day_items = forecast_list_container.select('li')
            logger.debug(f"在容器内找到 {len(day_items)} 个 10天预报列表元素")

            for i, item_elem in enumerate(day_items):
                try:
                    # Extract data based on the structure of <li> within .wea_list ul
                    weekday_elem = item_elem.select_one('span.week:nth-of-type(1)') # First span.week is weekday
                    date_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(7)') # Second span.week is date (MM/DD)
                    day_condition_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(2)') # First span.wea is day condition
                    night_condition_elem = item_elem.select_one('span.wea:nth-of-type(2)') # Second span.wea is night condition
                    temp_high_elem = item_elem.select_one('.tree b') # High temp is within .tree div > p > b
                    temp_low_elem = item_elem.select_one('.tree strong') # Low temp is within .tree div > p > strong
                    is_active = 'active' in item_elem.get('class', [])

                    weekday = weekday_elem.get_text(strip=True) if weekday_elem else None
                    date = date_elem.get_text(strip=True) if date_elem else None
                    day_condition = day_condition_elem.get_text(strip=True) if day_condition_elem else "未知状况"
                    night_condition = night_condition_elem.get_text(strip=True) if night_condition_elem else "未知状况"
                    temp_high = temp_high_elem.get_text(strip=True) if temp_high_elem else None
                    temp_low = temp_low_elem.get_text(strip=True) if temp_low_elem else None

                    # Basic validation: need at least weekday, date, and temps
                    # If any essential part is missing, log a warning and skip this item
                    if not all([weekday, date, temp_high, temp_low, day_condition, night_condition]):
                         logger.warning(f"跳过不完整的 10天预报项 (索引 {i}): Weekday='{weekday}', Date='{date}', High='{temp_high}',"
                                        f" Low='{temp_low}, "
                                        f"DayCondition='{day_condition}', NightCondition='{night_condition}'")
                         continue # Skip this item but continue parsing others

                    forecast_day = DetailedForecastDay(
                        weekday=weekday,
                        date=date,
                        day_condition=day_condition,
                        night_condition=night_condition,
                        temp_high=temp_high,
                        temp_low=temp_low,
                        is_active=is_active
                    )
                    forecast_list.append(forecast_day)
                    # logger.debug(f"解析到 10天预报项 (索引 {i}): {forecast_day}") # Avoid spamming
                except Exception as e:
                    logger.error(f"解析单个 10天预报项 (索引 {i}) 时发生错误: {e}", exc_info=True)

            logger.debug(f"共解析到 {len(forecast_list)} 个 10天预报项")

            # Return None if the list is empty even though the container was found
            return forecast_list if forecast_list else None

        except Exception as e:
            # Catch any unexpected errors during the overall _parse_10day_forecast function (e.g., selector error)
            logger.error(f"解析 10天预报列表时发生不可预测错误: {e}", exc_info=True)
            # Raise a specific parsing error indicating failure to parse the list
            raise ParsingError(f"解析 10天预报列表时发生不可预测错误: {e}") from e
    def _parse_7day_forecast(self, soup: BeautifulSoup) -> Optional[List[DetailedForecastDay]]:
        """
        Parses the 7-day forecast list from the #detail_future section.
        """
        logger.debug("正在解析 7天预报列表...")
        forecast_list = []
        try:
            # Select the container for the 7-day forecast items
            forecast_list_container = soup.select_one('#detail_future .detail_future_grid .wea_list ul')
            if not forecast_list_container:
                logger.warning("未能找到 7天预报列表容器 (#detail_future .detail_future_grid .wea_list ul)，HTML结构可能已改变。")
                return None # Return None if the main container is not found

            # Select individual list items within the container
            day_items = forecast_list_container.select('li')
            logger.debug(f"在容器内找到 {len(day_items)} 个 7天预报列表元素")

            for i, item_elem in enumerate(day_items):
                try:
                    # Extract data based on the structure of <li> within .wea_list ul
                    weekday_elem = item_elem.select_one('span.week:nth-of-type(1)') # First span.week is weekday
                    date_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(7)') # Second span.week is date (MM/DD)
                    day_condition_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(2)') # First span.wea is day condition
                    night_condition_elem = item_elem.select_one('span.wea:nth-of-type(2)') # Second span.wea is night condition
                    temp_high_elem = item_elem.select_one('.tree b') # High temp is within .tree div > p > b
                    temp_low_elem = item_elem.select_one('.tree strong') # Low temp is within .tree div > p > strong
                    is_active = 'active' in item_elem.get('class', [])

                    weekday = weekday_elem.get_text(strip=True) if weekday_elem else None
                    date = date_elem.get_text(strip=True) if date_elem else None
                    day_condition = day_condition_elem.get_text(strip=True) if day_condition_elem else "未知状况"
                    night_condition = night_condition_elem.get_text(strip=True) if night_condition_elem else "未知状况"
                    temp_high = temp_high_elem.get_text(strip=True) if temp_high_elem else None
                    temp_low = temp_low_elem.get_text(strip=True) if temp_low_elem else None

                    # Basic validation: need at least weekday, date, and temps
                    # If any essential part is missing, log a warning and skip this item
                    if not all([weekday, date, temp_high, temp_low, day_condition, night_condition]):
                         logger.warning(f"跳过不完整的 7天预报项 (索引 {i}): Weekday='{weekday}', Date='{date}', High='{temp_high}',"
                                        f" Low='{temp_low}, "
                                        f"DayCondition='{day_condition}', NightCondition='{night_condition}'")
                         continue # Skip this item but continue parsing others

                    forecast_day = DetailedForecastDay(
                        weekday=weekday,
                        date=date,
                        day_condition=day_condition,
                        night_condition=night_condition,
                        temp_high=temp_high,
                        temp_low=temp_low,
                        is_active=is_active
                    )
                    forecast_list.append(forecast_day)
                    # logger.debug(f"解析到 7天预报项 (索引 {i}): {forecast_day}") # Avoid spamming
                except Exception as e:
                    logger.error(f"解析单个 7天预报项 (索引 {i}) 时发生错误: {e}", exc_info=True)

            logger.debug(f"共解析到 {len(forecast_list)} 个 7天预报项")

            # Return None if the list is empty even though the container was found
            return forecast_list if forecast_list else None

        except Exception as e:
            # Catch any unexpected errors during the overall _parse_7day_forecast function (e.g., selector error)
            logger.error(f"解析 7天预报列表时发生不可预测错误: {e}", exc_info=True)
            # Raise a specific parsing error indicating failure to parse the list
            raise ParsingError(f"解析 7天预报列表时发生不可预测错误: {e}") from e

    def _parse_15day_forecast(self, soup: BeautifulSoup) -> Optional[List[DetailedForecastDay]]:
        """
        Parses the 15-day forecast list from the #detail_future section.
        """
        logger.debug("正在解析 15天预报列表...")
        forecast_list = []
        try:
            # Select the container for the 15-day forecast items
            forecast_list_container = soup.select_one('#detail_future .detail_future_grid .wea_list ul')
            if not forecast_list_container:
                logger.warning("未能找到 15天预报列表容器 (#detail_future .detail_future_grid .wea_list ul)，HTML结构可能已改变。")
                return None # Return None if the main container is not found

            # Select individual list items within the container
            day_items = forecast_list_container.select('li')
            logger.debug(f"在容器内找到 {len(day_items)} 个 15天预报列表元素")

            for i, item_elem in enumerate(day_items):
                try:
                    # Extract data based on the structure of <li> within .wea_list ul
                    weekday_elem = item_elem.select_one('span.week:nth-of-type(1)') # First span.week is weekday
                    date_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(7)') # Second span.week is date (MM/DD)
                    day_condition_elem = item_elem.select_one(f'#detail_future > div.detail_future_grid > div.wea_list.clearfix > ul > li:nth-child({i+1}) > span:nth-child(2)') # First span.wea is day condition
                    night_condition_elem = item_elem.select_one('span.wea:nth-of-type(2)') # Second span.wea is night condition
                    temp_high_elem = item_elem.select_one('.tree b') # High temp is within .tree div > p > b
                    temp_low_elem = item_elem.select_one('.tree strong') # Low temp is within .tree div > p > strong
                    is_active = 'active' in item_elem.get('class', [])

                    weekday = weekday_elem.get_text(strip=True) if weekday_elem else None
                    date = date_elem.get_text(strip=True) if date_elem else None
                    day_condition = day_condition_elem.get_text(strip=True) if day_condition_elem else "未知状况"
                    night_condition = night_condition_elem.get_text(strip=True) if night_condition_elem else "未知状况"
                    temp_high = temp_high_elem.get_text(strip=True) if temp_high_elem else None
                    temp_low = temp_low_elem.get_text(strip=True) if temp_low_elem else None

                    # Basic validation: need at least weekday, date, and temps
                    # If any essential part is missing, log a warning and skip this item
                    if not all([weekday, date, temp_high, temp_low, day_condition, night_condition]):
                         logger.warning(f"跳过不完整的 15天预报项 (索引 {i}): Weekday='{weekday}', Date='{date}', High='{temp_high}',"
                                        f" Low='{temp_low}, "
                                        f"DayCondition='{day_condition}', NightCondition='{night_condition}'")
                         continue # Skip this item but continue parsing others

                    forecast_day = DetailedForecastDay(
                        weekday=weekday,
                        date=date,
                        day_condition=day_condition,
                        night_condition=night_condition,
                        temp_high=temp_high,
                        temp_low=temp_low,
                        is_active=is_active
                    )
                    forecast_list.append(forecast_day)
                    # logger.debug(f"解析到 15天预报项 (索引 {i}): {forecast_day}") # Avoid spamming
                except Exception as e:
                    logger.error(f"解析单个 15天预报项 (索引 {i}) 时发生错误: {e}", exc_info=True)

            logger.debug(f"共解析到 {len(forecast_list)} 个 15天预报项")

            # Return None if the list is empty even though the container was found
            return forecast_list if forecast_list else None

        except Exception as e:
            # Catch any unexpected errors during the overall _parse_15day_forecast function (e.g., selector error)
            logger.error(f"解析 15天预报列表时发生不可预测错误: {e}", exc_info=True)
            # Raise a specific parsing error indicating failure to parse the list
            raise ParsingError(f"解析 15天预报列表时发生不可预测错误: {e}") from e