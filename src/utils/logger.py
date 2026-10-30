# utils/logger.py
import logging
from colorlog import ColoredFormatter

# 清理现有的处理器以避免重复
root_logger = logging.getLogger()
if root_logger.handlers:
    # 移除所有现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

# 自定义日志格式并添加颜色
formatter = ColoredFormatter(
    "%(asctime)s.%(msecs)03d %(log_color)s%(levelname)s%(reset)s %(name)s:%(lineno)d: %(message)s",
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG':    'cyan',
        'INFO':     'green',
        'WARNING':  'yellow',
        'ERROR':    'red',
        'CRITICAL': 'bold_red',
    }
)

# 配置根日志器
handler = logging.StreamHandler()
handler.setFormatter(formatter)

# 设置日志级别并添加处理器
root_logger.setLevel(logging.INFO)
root_logger.addHandler(handler)

def get_logger(name: str):
    return logging.getLogger(name)