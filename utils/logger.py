# Keep a log when in app form
import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger():
    # Create a log directory in the standard location
    log_dir = os.path.expanduser("~/Library/Logs/SallyClicks")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "sally.log")

    # Set up the logger
    logger = logging.getLogger("SallyClicks")
    logger.setLevel(logging.DEBUG)

    # File Handler 
    # Max 3 Files
    # Max 5 mb
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console handler for terminal
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Gglobal instance that can be imported anywhere
logger = setup_logger()