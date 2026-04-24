import logging
import time
import re
from logging.handlers import RotatingFileHandler

def clean_error_message(msg):
    return re.sub(r'at 0x[0-9A-Fa-f]+', 'at <ADDR>', msg)

class AntiFloodFilter(logging.Filter):
    def __init__(self, name='', cooldown=20):
        super().__init__(name)
        self.last_log_time = {}
        self.cooldown = cooldown

    def filter(self, record):
        now = time.time()
        key = f"{record.levelname}:{record.msg}"
        last = self.last_log_time.get(key, 0)
        if now - last > self.cooldown:
            self.last_log_time[key] = now
            return True
        return False

def setup_logger(log_file='agent.log'):
    logger = logging.getLogger("agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.addFilter(AntiFloodFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(AntiFloodFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Capture logs Tufup
    tufup_logger = logging.getLogger("tufup")
    tufup_logger.setLevel(logging.INFO)
    tufup_logger.addHandler(file_handler)
    tufup_logger.addHandler(console_handler)

    return logger
