# mojiweather_api/services.py

import httpx
from typing import List, Dict, Any, Optional, Tuple
from .logger import logger
from .html_scraper import MojiWeatherHTMLScraper
from .json_client import MojiWeatherJSONClient
from .models import (
    CurrentWeather,
    DailyForecastSummary,
    LifeIndex,
    CalendarDayForecast,
    Forecast24HourItem,
    DetailedForecastDay
)
from .exceptions import (
    InvalidLocationError,
    MojiWeatherAPIError,
    RequestFailedError,
    HTMLStructureError,
    JSONStructureError,
    ParsingError,
    AuthenticationError
)
from .config import HTML_BASE_URL # Import HTML_BASE_URL for referer

class WeatherService:
    """Provides weather data using different Moji Weather sources."""

    def __init__(self):
        logger.info("初始化 WeatherService")
        self.html_scraper = MojiWeatherHTMLScraper()
        self.json_client = MojiWeatherJSONClient()
        # httpx.AsyncClient will be created and managed within the chained method

    async def get_full_weather_data(self, city_slug: str, city_id_for_json: int) -> Dict[str, Any]:
        """
        Gets comprehensive weather data by first scraping the main HTML page and then
        fetching the 24-hour forecast JSON using the same session/cookies.
        This method does *not* include the 10-day forecast page.

        Args:
            city_slug: The URL slug for the city's main HTML page
                       (e.g., "guangdong/huangpu-district").
            city_id_for_json: The numeric ID for the city required by the
                              24-hour forecast JSON endpoint (e.g., 285123).

        Returns:
            A dictionary containing:
            - "html_data": Parsed data from the main HTML page
                           (dict with keys "current", "daily_summary", etc.).
                           Value is None if HTML scraping fails critically.
            - "json_24h_data": List of Forecast24HourItem objects from the JSON endpoint.
                             Value is None if JSON fetch or parsing fails.
            - "success": Boolean indicating if at least main HTML data was obtained successfully.

        Raises:
            InvalidLocationError: If location parameters are invalid or missing.
            RequestFailedError: If fetching the HTML page fails critically.
             HTMLStructureError: If main HTML parsing is severely unsuccessful (no core data).
             ParsingError: If parsing of a section within main HTML fails unexpectedly.
        """
        logger.info(f"调用 get_full_weather_data (主页+24h JSON): city_slug={city_slug}, city_id={city_id_for_json}")

        if not city_slug:
             logger.warning("get_full_weather_data: city_slug 参数不能为空")
             raise InvalidLocationError("city_slug 参数不能为空，请提供城市URL后缀")
        if not isinstance(city_id_for_json, int) or city_id_for_json <= 0:
             logger.warning(f"get_full_weather_data: 无效的 city_id_for_json 参数: {city_id_for_json}")
             raise InvalidLocationError(f"无效的城市ID: {city_id_for_json}")

        html_data = None
        html_page_actual_url = None
        json_24h_data = None
        overall_success = False

        # Use a single AsyncClient for potentially multiple requests that depend on cookies
        async with httpx.AsyncClient() as client:
            logger.debug("AsyncClient 实例创建，准备进行主 HTML 请求...")
            # --- Step 1: Fetch and Parse Main HTML Page ---
            try:
                html_data, html_page_actual_url = await self.html_scraper.fetch_and_parse_weather_page(city_slug, client)
                logger.info(f"成功获取和解析主 HTML 页面. Actual URL: {html_page_actual_url}")
                overall_success = True

            except (RequestFailedError, InvalidLocationError, HTMLStructureError) as e:
                logger.error(f"获取或解析主 HTML 页面失败: city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                # Re-raise critical errors related to main HTML fetch/parse needed for subsequent steps
                raise e
            except Exception as e:
                 logger.error(f"获取或解析主 HTML 页面时发生未知错误: city_slug={city_slug}, 错误: {e}", exc_info=True)
                 raise MojiWeatherAPIError(f"获取或解析主 HTML 页面时发生未知错误: {e}") from e

            # --- Step 2: Fetch and Parse 24-hour JSON data ---
            # Only attempt if HTML fetch was successful and we got the actual URL
            if overall_success and html_page_actual_url:
                 logger.debug(f"主 HTML 请求成功 ({html_page_actual_url})，准备进行 24小时 JSON 请求...")
                 try:
                     # Use the same client and the actual URL from the HTML response as Referer
                     json_24h_data = await self.json_client.fetch_24hour_forecast(city_id_for_json, html_page_actual_url, client)
                     logger.info("成功获取并解析 24小时预报 JSON 数据")

                 except (RequestFailedError, AuthenticationError, JSONStructureError, ParsingError, MojiWeatherAPIError) as e:
                     # Catch specific JSON errors, log them, but DO NOT re-raise here by default
                     logger.error(f"获取或解析 24小时预报 JSON 数据失败: city_id={city_id_for_json}, 错误: {e}", exc_info=True)
                 except Exception as e:
                      # Catch other unexpected errors from JSON client
                      logger.error(f"获取或解析 24小时预报 JSON 数据时发生未知错误: city_id={city_id_for_json}, 错误: {e}", exc_info=True)

        final_result = {
            "html_data": html_data,
            "json_24h_data": json_24h_data,
            "success": overall_success # Indicates if main HTML was successfully obtained/parsed critically
        }
        logger.info(f"get_full_weather_data 执行完成. 主 HTML 数据是否成功获取/解析: {overall_success}, 24小时 JSON 数据是否成功获取/解析: {'Yes' if json_24h_data is not None else 'No'}")
        return final_result

    async def get_10day_forecast_from_html(self, city_slug: str) -> Optional[List[DetailedForecastDay]]:
        """
        Gets the 10-day forecast by scraping the dedicated HTML page.
        Note: This method fetches the 10-day page independently. If it requires
        prior session/cookies from the main page, calling this standalone might fail.
        Consider using get_full_chained_weather_data instead.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").

        Returns:
            A list of DetailedForecastDay objects, or None if fetching/parsing fails critically.

        Raises:
             InvalidLocationError: If city_slug is invalid or missing.
            RequestFailedError: If fetching the HTML page fails.
             HTMLStructureError: If parsing the 10-day forecast list fails critically.
             ParsingError: For other parsing issues.
             MojiWeatherAPIError: For other unpredictable errors.
        """
        logger.info(f"调用 get_10day_forecast_from_html (standalone): city_slug={city_slug}")
        logger.warning("调用 get_10day_forecast_from_html (standalone)。注意：如果此接口依赖于主页的会话/cookies，单独调用可能失败。建议使用 get_full_chained_weather_data 方法。")

        if not city_slug:
             logger.warning("get_10day_forecast_from_html: city_slug 参数不能为空")
             raise InvalidLocationError("city_slug 参数不能为空，请提供城市URL后缀")

        # Referer for the 10-day forecast page can be the related main weather page.
        # Using HTML_BASE_URL + slug as a plausible referer source.
        referer_url = f"{HTML_BASE_URL}/{city_slug}"
        logger.debug(f"设置 10天预报请求的 Referer 为: {referer_url}")

        async with httpx.AsyncClient() as client:
            logger.debug("AsyncClient 实例创建，准备进行 10天预报 HTML 请求...")
            try:
                # Fetch and parse the 10-day forecast page, using the main page URL as referer
                forecast_list = await self.html_scraper.fetch_and_parse_10day_forecast(city_slug, client, referer_url)
                logger.info("成功获取并解析 10天预报 HTML 页面 (standalone)")
                return forecast_list

            except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                 logger.error(f"获取或解析 10天预报 HTML 页面失败 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 # Re-raise specific errors indicating failure
                 raise
            except Exception as e:
                 logger.error(f"获取或解析 10天预报 HTML 页面时发生未知错误 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True)
                 raise MojiWeatherAPIError(f"获取或解析 10天预报 HTML 页面时发生未知错误: {e}") from e

    async def get_7day_forecast_from_html(self, city_slug: str) -> Optional[List[DetailedForecastDay]]:
        """
        Gets the 7-day forecast by scraping the dedicated HTML page.
        Note: This method fetches the 7-day page independently. If it requires
        prior session/cookies from the main page, calling this standalone might fail.
        Consider using get_full_chained_weather_data instead.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").

        Returns:
            A list of DetailedForecastDay objects, or None if fetching/parsing fails critically.

        Raises:
             InvalidLocationError: If city_slug is invalid or missing.
            RequestFailedError: If fetching the HTML page fails.
             HTMLStructureError: If parsing the 7-day forecast list fails critically.
             ParsingError: For other parsing issues.
             MojiWeatherAPIError: For other unpredictable errors.
        """
        logger.info(f"调用 get_7day_forecast_from_html (standalone): city_slug={city_slug}")
        logger.warning("调用 get_7day_forecast_from_html (standalone)。注意：如果此接口依赖于主页的会话/cookies，单独调用可能失败。建议使用 get_full_chained_weather_data 方法。")

        if not city_slug:
             logger.warning("get_7day_forecast_from_html: city_slug 参数不能为空")
             raise InvalidLocationError("city_slug 参数不能为空，请提供城市URL后缀")

        # Referer for the 7-day forecast page can be the related main weather page.
        # Using HTML_BASE_URL + slug as a plausible referer source.
        referer_url = f"{HTML_BASE_URL}/{city_slug}"
        logger.debug(f"设置 7天预报请求的 Referer 为: {referer_url}")

        async with httpx.AsyncClient() as client:
            logger.debug("AsyncClient 实例创建，准备进行 7天预报 HTML 请求...")
            try:
                # Fetch and parse the 7-day forecast page, using the main page URL as referer
                forecast_list = await self.html_scraper.fetch_and_parse_7day_forecast(city_slug, client, referer_url)
                logger.info("成功获取并解析 7天预报 HTML 页面 (standalone)")
                return forecast_list

            except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                 logger.error(f"获取或解析 7天预报 HTML 页面失败 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 # Re-raise specific errors indicating failure
                 raise
            except Exception as e:
                 logger.error(f"获取或解析 7天预报 HTML 页面时发生未知错误 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True)
                 raise MojiWeatherAPIError(f"获取或解析 7天预报 HTML 页面时发生未知错误: {e}") from e

    async def get_15day_forecast_from_html(self, city_slug: str) -> Optional[List[DetailedForecastDay]]:
        """
        Gets the 15-day forecast by scraping the dedicated HTML page.
        Note: This method fetches the 15-day page independently. If it requires
        prior session/cookies from the main page, calling this standalone might fail.
        Consider using get_full_chained_weather_data instead.

        Args:
            city_slug: The URL slug for the city (e.g., "guangdong/huangpu-district").

        Returns:
            A list of DetailedForecastDay objects, or None if fetching/parsing fails critically.

        Raises:
             InvalidLocationError: If city_slug is invalid or missing.
            RequestFailedError: If fetching the HTML page fails.
             HTMLStructureError: If parsing the 15-day forecast list fails critically.
             ParsingError: For other parsing issues.
             MojiWeatherAPIError: For other unpredictable errors.
        """
        logger.info(f"调用 get_15day_forecast_from_html (standalone): city_slug={city_slug}")
        logger.warning("调用 get_15day_forecast_from_html (standalone)。注意：如果此接口依赖于主页的会话/cookies，单独调用可能失败。建议使用 get_full_chained_weather_data 方法。")

        if not city_slug:
             logger.warning("get_15day_forecast_from_html: city_slug 参数不能为空")
             raise InvalidLocationError("city_slug 参数不能为空，请提供城市URL后缀")

        # Referer for the 15-day forecast page can be the related main weather page.
        # Using HTML_BASE_URL + slug as a plausible referer source.
        referer_url = f"{HTML_BASE_URL}/{city_slug}"
        logger.debug(f"设置 15天预报请求的 Referer 为: {referer_url}")

        async with httpx.AsyncClient() as client:
            logger.debug("AsyncClient 实例创建，准备进行 15天预报 HTML 请求...")
            try:
                # Fetch and parse the 15-day forecast page, using the main page URL as referer
                forecast_list = await self.html_scraper.fetch_and_parse_15day_forecast(city_slug, client, referer_url)
                logger.info("成功获取并解析 15天预报 HTML 页面 (standalone)")
                return forecast_list

            except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                 logger.error(f"获取或解析 15天预报 HTML 页面失败 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 # Re-raise specific errors indicating failure
                 raise
            except Exception as e:
                 logger.error(f"获取或解析 15天预报 HTML 页面时发生未知错误 (standalone): city_slug={city_slug}, 错误: {e}", exc_info=True)
                 raise MojiWeatherAPIError(f"获取或解析 15天预报 HTML 页面时发生未知错误: {e}") from e

    async def get_full_chained_weather_data(self, city_slug: str, city_id_for_json: int) -> Dict[str, Any]:
        """
        Orchestrates fetching all weather data (main page, 24h json, 10-day)
        sequentially using a single client to preserve session/cookies.

        Order: Main HTML -> 24h JSON -> 10-day HTML.
        Referer for step 2 & 3 is the actual URL from step 1.

        Args:
            city_slug: The URL slug for the city's main HTML page and 10-day page
                       (e.g., "guangdong/huangpu-district").
            city_id_for_json: The numeric ID for the city required by the
                              24-hour forecast JSON endpoint (e.g., 285123).

        Returns:
            A dictionary containing:
            - "main_html_data": Parsed data from the main HTML page (dict). None if fetch/parse failed critically.
            - "json_24h_data": List of Forecast24HourItem objects. None if fetch/parse failed.
            - "ten_day_data": List of DetailedForecastDay objects. None if fetch/parse failed.
            - "seven_day_data": List of DetailedForecastDay objects. None if fetch/parse failed.
            - "fifteen_day_data": List of DetailedForecastDay objects. None if fetch/parse failed.
            - "success": Boolean indicating if at least the initial main HTML fetch/parse was successful (required for chain).

        Raises:
            InvalidLocationError: If location parameters are invalid or missing.
            RequestFailedError: If fetching the initial main HTML page fails.
             HTMLStructureError: If initial main HTML parsing fails critically.
             ParsingError: If initial main HTML parsing has other unexpected issues.
             # Subsequent errors (24h JSON, 10-day) are caught and logged,
             # resulting in None for their respective data fields.
        """
        logger.info(f"调用 get_full_chained_weather_data: city_slug={city_slug}, city_id={city_id_for_json}")

        if not city_slug:
             logger.warning("get_full_chained_weather_data: city_slug 参数不能为空")
             raise InvalidLocationError("city_slug 参数不能为空，请提供城市URL后缀")
        if not isinstance(city_id_for_json, int) or city_id_for_json <= 0:
             logger.warning(f"get_full_chained_weather_data: 无效的 city_id_for_json 参数: {city_id_for_json}")
             raise InvalidLocationError(f"无效的城市ID: {city_id_for_json}")

        main_html_data = None
        main_html_actual_url = None # To store the actual URL of the main HTML page
        json_24h_data = None
        ten_day_data = None
        seven_day_data = None
        fifteen_day_data = None
        overall_success = False # Indicates if the initial, critical step succeeded

        # Use a single AsyncClient for the entire chain of requests
        async with httpx.AsyncClient() as client:
            logger.debug("AsyncClient 实例创建，准备进行按顺序的请求链...")

            # --- Step 1: Fetch and Parse Main HTML Page ---
            logger.info("开始获取主天気 HTML 页面...")
            try:
                main_html_data, main_html_actual_url = await self.html_scraper.fetch_and_parse_weather_page(city_slug, client)
                logger.info(f"主 HTML 页面获取和解析成功。实际 URL: {main_html_actual_url}")
                overall_success = True # The first step succeeded

            except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                logger.error(f"获取或解析主 HTML 页面失败，中断后续请求链: city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                # If the very first step fails critically, re-raise because we can't proceed
                raise e
            except Exception as e:
                 logger.error(f"获取或解析主 HTML 页面时发生未知错误，中断后续请求链: city_slug={city_slug}, 错误: {e}", exc_info=True)
                 raise MojiWeatherAPIError(f"获取或解析主 HTML 页面时发生未知错误: {e}") from e

            # --- Step 2: Fetch and Parse 24-hour JSON data ---
            # Only attempt if step 1 was successful and we have the actual URL
            if overall_success and main_html_actual_url:
                 logger.info(f"主 HTML 请求成功 ({main_html_actual_url})，开始进行 24小时 JSON 请求...")
                 try:
                     # Use the same client and the actual URL from step 1 as Referer
                     json_24h_data = await self.json_client.fetch_24hour_forecast(city_id_for_json, main_html_actual_url, client)
                     logger.info("24小时预报 JSON 数据获取并解析成功")

                 except (RequestFailedError, AuthenticationError, JSONStructureError, ParsingError, MojiWeatherAPIError) as e:
                     # Catch specific JSON errors, log them, but DO NOT re-raise here
                     # Failure in this step should not stop the next step (10-day forecast)
                     logger.error(f"获取或解析 24小时预报 JSON 数据失败: city_id={city_id_for_json}, 错误: {e}", exc_info=True)
                 except Exception as e:
                      logger.error(f"获取或解析 24小时预报 JSON 数据时发生未知错误: city_id={city_id_for_json}, 错误: {e}", exc_info=True)

            # --- Step 3: Fetch and Parse 7, 10, 15-day HTML data ---
            # Only attempt if step 1 was successful and we have the actual URL
            # Assuming this also needs session/cookies from step 1
            if overall_success and main_html_actual_url:
                 logger.info(f"准备进行 7天预报 HTML 请求，使用 Referer: {main_html_actual_url}")
                 try:
                     # Use the same client and the actual URL from step 1 as Referer
                     seven_day_data = await self.html_scraper.fetch_and_parse_7day_forecast(city_slug, client, main_html_actual_url)
                     logger.info("7天预报 HTML 页面获取并解析成功")

                 except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                      # Catch specific HTML scraping/parsing errors for the 7-day page
                      # Failure in this step should not stop the overall process if previous steps succeeded
                      logger.error(f"获取或解析 7天预报 HTML 页面失败: city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 except Exception as e:
                      logger.error(f"获取或解析 7天预报 HTML 页面时发生未知错误: city_slug={city_slug}, 错误: {e}", exc_info=True)
                      raise MojiWeatherAPIError(f"获取或解析 7天预报 HTML 页面时发生未知错误: {e}") from e

            if overall_success and main_html_actual_url:
                 logger.info(f"准备进行 10天预报 HTML 请求，使用 Referer: {main_html_actual_url}")
                 try:
                     # Use the same client and the actual URL from step 1 as Referer
                     ten_day_data = await self.html_scraper.fetch_and_parse_10day_forecast(city_slug, client, main_html_actual_url)
                     logger.info("10天预报 HTML 页面获取并解析成功")

                 except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                      # Catch specific HTML scraping/parsing errors for the 10-day page
                      # Failure in this step should not stop the overall process if previous steps succeeded
                      logger.error(f"获取或解析 10天预报 HTML 页面失败: city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 except Exception as e:
                      logger.error(f"获取或解析 10天预报 HTML 页面时发生未知错误: city_slug={city_slug}, 错误: {e}", exc_info=True)
                      raise MojiWeatherAPIError(f"获取或解析 10天预报 HTML 页面时发生未知错误: {e}") from e

            if overall_success and main_html_actual_url:
                 logger.info(f"准备进行 15天预报 HTML 请求，使用 Referer: {main_html_actual_url}")
                 try:
                     # Use the same client and the actual URL from step 1 as Referer
                     fifteen_day_data = await self.html_scraper.fetch_and_parse_15day_forecast(city_slug, client, main_html_actual_url)
                     logger.info("15天预报 HTML 页面获取并解析成功")

                 except (RequestFailedError, InvalidLocationError, HTMLStructureError, ParsingError) as e:
                      # Catch specific HTML scraping/parsing errors for the 15-day page
                      # Failure in this step should not stop the overall process if previous steps succeeded
                      logger.error(f"获取或解析 15天预报 HTML 页面失败: city_slug={city_slug}, 错误: {e}", exc_info=True if not isinstance(e, InvalidLocationError) else False)
                 except Exception as e:
                      logger.error(f"获取或解析 15天预报 HTML 页面时发生未知错误: city_slug={city_slug}, 错误: {e}", exc_info=True)
                      raise MojiWeatherAPIError(f"获取或解析 15天预报 HTML 页面时发生未知错误: {e}") from e


        # Return a dictionary with all results
        final_result = {
            "main_html_data": main_html_data,
            "json_24h_data": json_24h_data,
            "ten_day_data": ten_day_data,
            "seven_day_data": seven_day_data,
            "fifteen_day_data": fifteen_day_data,
            "success": overall_success # Indicates if the chain could start (step 1 success)
        }
        logger.info(f"get_full_chained_weather_data 执行完成.")
        logger.debug(f"结果摘要: 主 HTML 成功: {main_html_data is not None}, 24h JSON 成功: {json_24h_data is not None}, 10天预报成功: {ten_day_data is not None}")
        return final_result

    # Keep or remove individual scraper/client access methods if they aren't needed publicly
    # (e.g., get_current_weather_from_html, get_24hour_forecast_from_api_standalone)
    # For this example, let's make the combined method the primary one and keep get_10day_forecast_from_html public
    # With a warning about standalone usage. get_full_weather_data covers main+24h.