# mojiweather_api/config.py

import configparser
import os
from .logger import logger

def load_config():
    """
    加载配置文件。
    尝试从环境变量指定的MOJIWEATHER_CONFIG_PATH或默认的config.ini加载。
    如果加载失败，返回一个空的ConfigParser实例。
    """
    logger.info("尝试加载配置文件...")
    config = configparser.ConfigParser()
    # 优先从环境变量获取配置路径
    config_path = os.environ.get('MOJIWEATHER_CONFIG_PATH', 'config.ini')

    # 从环境变量获取 API KEY 如果存在
    api_key_env = os.environ.get('MOJIWEATHER_API_KEY')
    if api_key_env:
        # 创建一个临时的section来存储环境变量中的API Key
        if not config.has_section('api'):
            config.add_section('api')
        config.set('api', 'api_key', api_key_env)
        logger.debug("从环境变量 MOJIWEATHER_API_KEY 加载 API Key")

    if not os.path.exists(config_path):
        if not api_key_env: # Only warn if no env var key either
            logger.warning(f"配置文件未找到或路径无效: {config_path}. 且未设置 MOJIWEATHER_API_KEY 环境变量。")
        else:
             logger.warning(f"配置文件未找到或路径无效: {config_path}.")
        return config # 返回空配置 (可能只包含环境变量加载的key)

    try:
        # 读取配置文件，环境变量中的值会覆盖同名配置文件的值 if api_key_env was set first
        config.read(config_path)
        logger.info(f"配置文件加载成功: {config_path}")

        # 如果环境变量中设置了 API Key，确保它覆盖配置文件中的值
        if api_key_env:
             if not config.has_section('api'):
                 config.add_section('api')
             config.set('api', 'api_key', api_key_env) # 再次设置，确保覆盖读取的文件内容
             logger.debug("环境变量中的 MOJIWEATHER_API_KEY 覆盖了配置文件中的值")

        return config
    except configparser.Error as e:
        logger.error(f"加载配置文件时发生错误: {config_path}, 错误详情: {e}", exc_info=True)
        # If file loading failed but env var key was obtained, return the config object
        if api_key_env and config.has_section('api') and config.has_option('api', 'api_key'):
             logger.warning("配置文件加载失败，但仍将使用环境变量中加载的 API Key。")
             return config
        else:
             logger.error("配置文件加载失败且未设置环境变量 API Key，将返回空配置。")
             return configparser.ConfigParser() # Return a brand new empty config

# 实例化一个配置对象，可在其他模块导入使用
# This ensures configuration is loaded once when the module is first imported
config = load_config()

# Define helper function to get config values
def get_config(section, key, fallback=None):
    """
    从加载的配置中获取值。
    """
    try:
        value = config.get(section, key)
        # Log sensitively
        if 'key' in key.lower() or 'password' in key.lower():
            logger.debug(f"获取配置项: [{section}].{key} = ******")
        else:
            logger.debug(f"获取配置项: [{section}].{key} = {value}")
        return value
    except (configparser.NoSectionError, configparser.NoOptionError):
        if fallback is not None:
            logger.debug(f"配置项 [{section}].{key} 未找到，使用fallback值: {fallback}")
            return fallback
        else:
            # Log error but avoid printing stack trace for often expected missing optional configs
            logger.error(f"配置项 [{section}].{key} 未找到且无fallback值", exc_info=False)
            raise # Re-raise the specific error for downstream handling
    except Exception as e:
        logger.error(f"获取配置项 [{section}].{key} 时发生未知错误: {e}", exc_info=True)
        raise

# Get API related settings from config
# API_KEY = get_config('api', 'api_key', fallback=None) # API Key potentially not needed for scraping
HTML_BASE_URL = get_config('api', 'html_base_url', fallback='https://tianqi.moji.com/weather/china') # Base URL for main weather page
JSON_BASE_URL = get_config('api', 'json_base_url', fallback='https://tianqi.moji.com/index/getHour24') # Base URL for 24h JSON API
# Corrected fallback based on the actual forecast10 URL structure provided
FORECAST10_BASE_URL = get_config('api', 'forecast10_base_url', fallback='https://tianqi.moji.com/forecast10/china') # Base URL for 10-day forecast page
FORECAST7_BASE_URL = get_config('api', 'forecast7_base_url', fallback='https://tianqi.moji.com/forecast7/china') # Base URL for 7-day forecast page
FORECAST15_BASE_URL = get_config('api', 'forecast15_base_url', fallback='https://tianqi.moji.com/forecast15/china') # Base URL for 15-day forecast page
REQUEST_TIMEOUT = int(get_config('api', 'request_timeout', fallback=10)) # Ensure timeout is an integer