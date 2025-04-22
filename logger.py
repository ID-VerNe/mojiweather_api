# mojiweather_api/logger.py

import logging
import os
import configparser

# 默认日志配置，如果config.ini读取失败，则使用此默认配置
DEFAULT_LOG_LEVEL = logging.INFO
DEFAULT_LOG_FORMAT = '[%(asctime)s] [%(levelname)s] [%(name)s.%(funcName)s] - %(message)s'
DEFAULT_LOG_FILENAME = None # 默认不输出到文件

# 尝试从config加载日志配置
try:
    # 假设 config.ini 在项目根目录或可以通过环境变量指定路径
    config_path = os.environ.get('MOJIWEATHER_CONFIG_PATH', 'config.ini')
    config = configparser.ConfigParser()
    config.read(config_path)

    log_level_str = config.get('logging', 'level', fallback='INFO')
    log_format = config.get('logging', 'format', fallback=DEFAULT_LOG_FORMAT)
    log_filename = config.get('logging', 'filename', fallback=DEFAULT_LOG_FILENAME)

    log_level = getattr(logging, log_level_str.upper(), DEFAULT_LOG_LEVEL)

except (configparser.Error, FileNotFoundError) as e:
    # 如果配置读取失败，使用默认值并记录警告
    log_level = DEFAULT_LOG_LEVEL
    log_format = DEFAULT_LOG_FORMAT
    log_filename = DEFAULT_LOG_FILENAME
    print(f"[WARNING] Failed to load logging configuration from config.ini: {e}. Using default logging settings.")

# 配置基础日志系统
logging_config = {
    'level': log_level,
    'format': log_format,
}
if log_filename:
    logging_config['filename'] = log_filename

logging.basicConfig(**logging_config)

# 获取包内使用的logger实例
logger = logging.getLogger(__name__)

logger.info("日志系统初始化完成.")