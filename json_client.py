# mojiweather_api/json_client.py

from typing import List, Dict, Any

import httpx

from .config import JSON_BASE_URL, REQUEST_TIMEOUT  # Import base URL, API Key, and timeout from config
from .exceptions import RequestFailedError, AuthenticationError, JSONStructureError, MojiWeatherAPIError, ParsingError
from .logger import logger
from .models import Forecast24HourItem


class MojiWeatherJSONClient:
    """Fetches weather data from Moji Weather JSON endpoints."""

    def __init__(self):
        logger.info("初始化 MojiWeatherJSONClient")
        # self.api_key = API_KEY # Potentially needed for JSON endpoints, but not for getHour24 based on headers
        self.base_url = JSON_BASE_URL  # Base URL for JSON APIs
        # No API Key header needed based on user's request sample for getHour24

    async def fetch_24hour_forecast(self, city_id: int, html_referer_url: str, client: httpx.AsyncClient) -> List[
        Forecast24HourItem]:
        """
        Fetches 24-hour forecast data from the JSON endpoint.

        Args:
            city_id: The numeric ID for the city required by the JSON endpoint.
            html_referer_url: The URL of the HTML page request that happened just before.
            client: An httpx.AsyncClient instance to use for the request.

        Returns:
            A list of Forecast24HourItem objects.

        Raises:
            RequestFailedError: If the HTTP request fails.
            AuthenticationError: If authentication fails (e.g., 401 status).
            JSONStructureError: If the JSON structure is unexpected.
             ParsingError: If data inside JSON cannot be parsed.
            MojiWeatherAPIError: For other unexpected errors.
        """
        logger.info(f"正在获取24小时天气预报 JSON 数据: city_id={city_id}")

        # Verify JSON_BASE_URL is configured
        if 'REPLACE_WITH_ACTUAL_24HOUR_JSON_URL' in self.base_url or not self.base_url:
            logger.error("JSON_BASE_URL 未在 config.ini 中配置，或配置错误。请更新配置。")
            # Decide if this should be a config error vs API error
            raise MojiWeatherAPIError("24小时预报 JSON_BASE_URL 未配置")

        endpoint = self.base_url  # JSON_BASE_URL should contain the full path like https://tianqi.moji.com/index/getHour24
        params = {"city_id": city_id}  # Assuming city_id is a query parameter as used in example.py

        # Add necessary browser-like headers for the JSON request based on your provided details
        json_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
            "Accept": "*/*",  # As seen in the request header
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,it;q=0.7,ko;q=0.6",
            "Referer": html_referer_url,  # Crucially, set the Referer to the HTML page URL
            "X-Requested-With": "XMLHttpRequest",  # Mimic AJAX request
            "Connection": "keep-alive",
            "DNT": "1",
            "Sec-GPC": "1",
            "Sec-Fetch-Dest": "empty",  # As seen in the request header
            "Sec-Fetch-Mode": "cors",  # As seen in the request header
            "Sec-Fetch-Site": "same-origin",  # As seen in the request header
            # Cookies are handled automatically by the httpx.AsyncClient instance
        }
        logger.debug(f"发送 JSON 请求头: {json_headers}")
        logger.debug(f"目标 JSON URL: {endpoint}, Params: {params}")

        try:
            response = await client.get(endpoint, params=params, headers=json_headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()  # Raises HTTPStatusError for bad responses (4xx or 5xx)
            logger.info(f"成功获取24小时预报 JSON: URL={endpoint}, Status Code={response.status_code}")
            logger.debug(f"接收到 JSON 响应头: {response.headers}")
            # Note: Response Content-Type is text/html; charset=UTF-8, but body is JSON. This is common pattern.

            raw_data: Dict[str, Any] = response.json()
            # Log raw data only at DEBUG level to avoid clutter/sensitive info in INFO logs
            logger.debug(f"原始 24小时预报 JSON 数据: {raw_data}")

            # Assuming the 24-hour forecast is in a list under the key "hour24"
            hour24_list_raw = raw_data.get('hour24')
            if not isinstance(hour24_list_raw, list):
                logger.error(
                    f"JSON 结构异常，未找到 key 'hour24' 或其值不是列表. 原始数据类型 '{type(raw_data.get('hour24'))}', 原始数据键: {raw_data.keys()}")
                raise JSONStructureError("JSON 响应结构异常，未找到或解析 'hour24' 列表")

            forecast_list = [Forecast24HourItem.from_json(item) for item in hour24_list_raw]
            logger.info(f"成功解析 {len(forecast_list)} 个24小时预报项")
            return forecast_list

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 错误获取24小时预报: URL={endpoint}, Status: {e.response.status_code}, 错误详情: {e}",
                         exc_info=True)
            if e.response.status_code == 401:
                raise AuthenticationError(
                    "API 认证失败，请检查您的API Key (getHour24 endpoint likely does not require a formal API Key, but check documentation just in case, more likely session/cookie issue)") from e
            # You might add checks for other specific status codes if Moji API documentation exists
            raise RequestFailedError(f"获取24小时预报 HTTP 错误 (状态码 {e.response.status_code}): {e}") from e
        except httpx.RequestError as e:
            if isinstance(e, httpx.ConnectTimeout) or isinstance(e, httpx.ReadTimeout):
                logger.error(f"获取24小时预报超时: URL={endpoint}", exc_info=True)
                raise RequestFailedError(f"获取24小时预报超时: {e}") from e
            else:
                logger.error(f"网络或请求错误获取24小时预报: URL={endpoint}, 错误详情: {e}", exc_info=True)
            raise RequestFailedError(f"获取24小时预报请求失败: {e}") from e
        except JSONStructureError:
            raise  # Re-raise the specifically caught JSONStructureError
        except ParsingError:
            raise  # Re-raise the specifically caught ParsingError from model parsing
        except Exception as e:
            logger.error(f"处理或解析24小时预报 JSON 数据时发生未知错误: URL={endpoint}, 错误详情: {e}", exc_info=True)
            raise MojiWeatherAPIError(f"处理24小时预报数据时发生未知错误: {e}") from e
