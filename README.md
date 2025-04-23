# mojiweather-api [![PyPI - Version](https://img.shields.io/pypi/v/mojiweather-api)](https://pypi.org/project/mojiweather-api/)

一个用于获取墨迹天气网站天气数据的 Python 包。

**重要提示：本包通过抓取墨迹天气网站的公开页面和潜在的非公开接口获取数据，而非使用墨迹官方提供的稳定 API。**

**特点：**

*   获取城市实时天气信息。
*   获取城市 24小时逐小时天气预报数据。
*   获取城市未来 7、10、15天天气预报列表。
*   支持异步请求 (`httpx`)。
*   包含日志记录，易于调试和监控。
*   通过配置文件管理关键 URL 和参数。
*   实现链式请求，处理数据源之间的依赖关系 (例如，JSON 数据和长时效预报页面可能依赖于先访问主页以建立会话)。

**注意：**

由于本包依赖于解析墨迹天气网站的 HTML 结构和接口行为，网站改版可能导致本包失效。此外，抓取网站数据可能违反其服务条款，请谨慎使用并自行承担风险。特别是代码中用于解析天气列表等部分使用了 `nth-child` 等方式定位元素，这种方式使得解析逻辑更加脆弱，极易受页面细微结构变化影响。

## 安装

您可以通过 pip 直接从 PyPI 安装本包：

```bash
pip install mojiweather-api
```

或者，如果您想从源代码安装：

1.  **克隆仓库：**
    ```bash
    git clone https://github.com/ID-VerNe/mojiweather_api.git
    ```
2.  **进入项目目录：**
    ```bash
    cd mojiweather_api
    ```
3.  **安装依赖（如果从源码运行而非打包安装）：**
    本包依赖 `httpx` 和 `beautifulsoup4`。
    ```bash
    pip install httpx beautifulsoup4
    ```
4.  **（可选）在本地进行可编辑安装：**
    ```bash
    pip install -e .
    ```

## 配置

本包通过 `config.ini` 文件进行配置。

1.  在您的项目根目录或可通过环境变量 `MOJIWEATHER_CONFIG_PATH` 指定的位置创建 `config.ini` 文件。
2.  填写配置信息：

    ```ini
    [api]
    # 墨迹天气网页天气详情页的基础URL
    html_base_url = https://tianqi.moji.com/weather/china

    # 墨迹天气24小时预报JSON接口的基础URL
    # 请根据实际抓包结果填写这个URL
    json_base_url = https://tianqi.moji.com/index/getHour24

    # 墨迹天气 7天预报页面的基础URL
    forecast7_base_url = https://tianqi.moji.com/forecast7/china

    # 墨迹天气 10天预报页面的基础URL
    forecast10_base_url = https://tianqi.moji.com/forecast10/china

    # 墨迹天气 15天预报页面的基础URL
    forecast15_base_url = https://tianqi.moji.com/forecast15/china

    # 请求超时时间 (秒)
    request_timeout = 10

    # 如果墨迹天气提供了需要API Key的官方接口，可以在此配置（当前抓取方式可能不需要）
    # api_key = YOUR_MOJI_WEATHER_API_KEY


    [logging]
    # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
    level = INFO
    # 日志格式
    format = [%(asctime)s] [%(levelname)s] [%(name)s.%(funcName)s] - %(message)s
    # 日志输出文件 (可选，不填则输出到控制台)
    # filename = mojiweather.log
    ```

3.  您可以通过设置环境变量 `MOJIWEATHER_CONFIG_PATH` 指定配置文件的路径。

## 使用示例

本包提供了 `get_full_chained_weather_data` 函数，用于按顺序获取主页数据、24小时预报和长时效预报，以处理数据源之间的依赖关系和会话维持。

首先，确保您已经根据上述步骤安装了包并创建了 `config.ini` 文件。

接着，在您的 Python 脚本中使用以下代码：

```python
import asyncio
import os # 用于设置可能的配置路径环境变量
# 从安装的包中导入所需的函数、模型和异常
from mojiweather_api import (
    get_full_chained_weather_data,
    MojiWeatherAPIError,
    InvalidLocationError,
    RequestFailedError,
    HTMLStructureError,
    JSONStructureError,
    ParsingError,
    logger
    # 您也可以导入具体的模型类，如 CurrentWeather, DetailedForecastDay 等
)

# **重要：确保 config.ini 文件在脚本能找到的位置！**
# 如果 config.ini 不在当前目录，可以通过设置环境变量指定路径：
# os.environ['MOJIWEATHER_CONFIG_PATH'] = '/path/to/your/config.ini'

async def main():
    logger.info("示例程序开始运行")

    # 指定查询的城市
    # city_slug: 城市在墨迹天气网站URL中的后缀，如 "guangdong/huangpu-district"
    # city_id_for_json: 24小时JSON接口所需的城市数字ID，例如黄埔区可能是 285123
    #                   请根据实际抓包或其他方式确定正确的城市ID。
    city_slug = "guangdong/huangpu-district"
    city_id_for_json = 285123

    logger.info(f"正在获取 {city_slug} (24h JSON ID: {city_id_for_json}) 的所有天气数据...")

    try:
        # 调用链式获取所有天气数据的方法
        all_data = await get_full_chained_weather_data(city_slug, city_id_for_json)

        print("\n--- 获取结果 ---")
        # the 'success' key indicates if the initial (main html) request was successful
        if not all_data.get("success"):
             print("\n警告: 主页数据未能获取，后续依赖主页的请求可能失败。")

        # 检查和打印 主页 HTML 数据
        main_html_data = all_data.get("main_html_data")
        if main_html_data:
            print("== 主页 HTML 数据 ==")
            current = main_html_data.get("current")
            if current and any([current.temperature, current.condition]):
                print(f"当前天气: 温度={current.temperature}, 状况={current.condition}, 湿度={current.humidity}, 风力={current.wind}, 更新于={current.update_time}, AQI={current.aqi}")
            else:
                 print("  主页 HTML: 未能找到或解析当前天气数据 section。")

            daily_summary = main_html_data.get("daily_summary")
            if daily_summary:
                 print("每日预报摘要 (主页):")
                 for i, day in enumerate(daily_summary):
                     # 打印前几天的摘要，或全部
                     print(f"  [{i+1}] {day.day_name}: {day.condition}, {day.temp_range}, {day.wind}{day.wind_level}, AQI {day.aqi}")
            else:
                 print("  主页 HTML: 未能解析出每日预报摘要。")

            life_indices = main_html_data.get("life_indices")
            if life_indices:
                 print("生活指数 (主页):")
                 for index in life_indices:
                      print(f"  {index.title}: {index.level}")
            else:
                 print("  主页 HTML: 未能解析出生活指数。")

            calendar_data = main_html_data.get("calendar")
            if calendar_data:
                 print("天气日历 (主页):")
                 for day in calendar_data:
                      print(f"  日 {day.day_of_month}: {day.condition}, {day.temp_range}, {day.wind} (当前={day.is_active})")
            else:
                 print("  主页 HTML: 未能解析出天气日历。")
        else:
             print("主页 HTML 数据获取或解析失败。")

        print("-" * 30)

        # 检查和打印 24小时 JSON 预报数据
        json_24h_data = all_data.get("json_24h_data")
        if json_24h_data:
            print("\n== 24小时 JSON 预报数据 ==")
            for hour_item in json_24h_data:
                print(f"  {hour_item.predict_date} {hour_item.predict_hour:02d}时: {hour_item.temperature}°C, {hour_item.condition}, 风力等级 {hour_item.wind_level}, 湿度 {hour_item.humidity}%")
            print(f"  总共 {len(json_24h_data)} 项")
        else:
             print("\n24小时 JSON 数据获取或解析失败。详情参见日志。")

        print("-" * 30)

        # 检查和打印 7天预报数据
        seven_day_data = all_data.get("seven_day_data")
        if seven_day_data:
            print("\n== 7天预报数据 ==")
            for day in seven_day_data:
                print(f"  {day.weekday} {day.date}: 白天 {day.day_condition}, 夜间 {day.night_condition}, 温度 {day.temp_low} ~ {day.temp_high} (当前={day.is_active})")
            print(f"  总共 {len(seven_day_data)} 项")
        else:
             print("\n7天预报数据获取或解析失败。详情参见日志。")

        print("-" * 30)

        # 检查和打印 10天预报数据
        ten_day_data = all_data.get("ten_day_data")
        if ten_day_data:
            print("\n== 10天预报数据 ==")
            for day in ten_day_data:
                print(f"  {day.weekday} {day.date}: 白天 {day.day_condition}, 夜间 {day.night_condition}, 温度 {day.temp_low} ~ {day.temp_high} (当前={day.is_active})")
            print(f"  总共 {len(ten_day_data)} 项")
        else:
             print("\n10天预报数据获取或解析失败。详情参见日志。")

        print("-" * 30)

         # 检查和打印 15天预报数据
        fifteen_day_data = all_data.get("fifteen_day_data")
        if fifteen_day_data:
            print("\n== 15天预报数据 ==")
            for day in fifteen_day_data:
                print(f"  {day.weekday} {day.date}: 白天 {day.day_condition}, 夜间 {day.night_condition}, 温度 {day.temp_low} ~ {day.temp_high} (当前={day.is_active})")
            print(f"  总共 {len(fifteen_day_data)} 项")
        else:
             print("\n15天预报数据获取或解析失败。详情参见日志。")

        print("-" * 30)


    # 捕获并处理可能发生的异常
    except InvalidLocationError as e:
        logger.error(f"获取天气数据失败 (无效位置参数): {e}")
        print(f"\n错误: 无效的城市参数 - {e}")
    except RequestFailedError as e:
        logger.error(f"获取天气数据失败 (HTTP 请求错误): {e}", exc_info=True)
        print(f"\n错误: 请求天气数据失败 - {e}")
    except HTMLStructureError as e:
        logger.error(f"获取天气数据失败 (HTML 结构变化): {e}", exc_info=True)
        print(f"\n错误: 解析 HTML 页面结构出错，网站可能已改版 - {e}")
    except ParsingError as e:
        logger.error(f"获取天气数据失败 (数据解析错误): {e}", exc_info=True)
        print(f"\n错误: 数据解析出错 - {e}")
    except MojiWeatherAPIError as e:
         logger.error(f"获取天气数据失败 (通用 API 错误): {e}", exc_info=True)
         print(f"\n错误: API 调用失败 - {e}")
    except Exception as e:
        logger.critical(f"获取天气数据发生未处理的未知错误: {e}", exc_info=True)
        print(f"\n发生未处理的未知错误: {e}")

    logger.info("示例程序执行结束")

if __name__ == "__main__":
    # 在主程序入口处运行异步函数
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"程序根级别发生未处理的错误: {e}", exc_info=True)
        print(f"程序运行发生未处理的错误: {e}")

```

## 数据模型

本包中定义了多个数据模型类 (位于 `mojiweather_api/models.py`) 来结构化获取到的天气数据。这些是标准 Python `@dataclass`，方便访问获取到的数据字段。

*   `CurrentWeather`: 实时天气信息 (温度、状况、湿度、风力、更新时间、AQI)。
*   `DailyForecastSummary`: 主页上显示的每日预报摘要 (通常是最近几天的简要信息)。
*   `LifeIndex`: 生活指数项 (标题、级别)。
*   `CalendarDayForecast`: 主页天气日历中的每日信息。
*   `Forecast24HourItem`: 24小时预报中的逐小时数据。
*   `DetailedForecastDay`: 7、10、15天预报列表中每日的详细信息 (星期、日期、昼夜状况、最高/最低温度)。

请参考 `mojiweather_api/models.py` 文件查看每个模型的详细字段。

## 错误处理

包中定义了自定义异常 (位于 `mojiweather_api/exceptions.py`)，以便用户能够根据不同的错误类型进行处理：

*   `MojiWeatherAPIError`: 所有包相关错误的基类。
*   `AuthenticationError`: 认证失败（虽然目前抓取方式可能不直接涉及 API Key 认证，但保留）。
*   `InvalidLocationError`: 提供的城市参数无效（例如，city\_slug 或 city\_id 导致找不到页面/数据）。
*   `RequestFailedError`: HTTP 请求失败（网络问题、超时、非 4xx/5xx 状态码但请求失败）。
*   `ParsingError`: 数据解析失败（基类）。
*   `HTMLStructureError`: HTML 结构与预期不符导致关键数据无法解析。
*   `JSONStructureError`: JSON 格式或结构与预期不符。

通过 `get_full_chained_weather_data` 获取数据时，如果在链条的第一个环节（获取主页 HTML）发生 `RequestFailedError`, `InvalidLocationError`, `HTMLStructureError`, `ParsingError` 或 `MojiWeatherAPIError`，函数会向上抛出这些异常，因为主页是后续请求的基础。

对于链条后续环节（24小时 JSON, 7/10/15天 HTML）的获取或解析失败，异常会在内部捕获并详细记录到日志中，函数不会中断，而是在返回字典中将对应的数据部分设置为 `None`。这样允许用户获取部分成功的数据。

在您的使用代码中，应该使用 `try...except` 块来捕获这些自定义异常并进行相应的处理。

## 日志记录

包内部使用了 Python 标准库的 `logging` 模块进行详细的日志记录。您可以根据 `config.ini` 中的 `[logging]` 配置来控制日志的详细程度 (`level`) 和输出位置 (`filename`)。

## 许可证

本项目使用 [MIT 许可证](LICENSE) 发布。
