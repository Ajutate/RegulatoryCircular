import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging():
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "app.log")
    
    import sys
    
    # Configure the rotating file handler: 5MB max, 5 backup files, force UTF-8
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    
    # Force sys.stdout to handle utf-8 if on Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Configure console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Define log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Suppress annoying passlib/bcrypt __about__ warning
    logging.getLogger("passlib").setLevel(logging.ERROR)
    
    # Prevent adding handlers multiple times if this is called more than once
    if not root_logger.handlers:
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    else:
        # If handlers already exist (e.g. from uvicorn or uvicorn reloading), 
        # ensure our file handler is there
        has_file_handler = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
        if not has_file_handler:
            root_logger.addHandler(file_handler)

def get_logger(name: str):
    return logging.getLogger(name)

# Ensure logging is setup when this module is imported
setup_logging()
