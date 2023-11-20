# work in proqress


import logging
from pathlib import Path
from datetime import datetime

def configure_logging(log_file=None, stream_handler=True, level=logging.INFO):
    """
    Configures the root logger for logging messages to the console
    and optionally to a specified log file. For usage in main scripts only (e.g. a psychopy experiment)

    This function sets up a logger with custom formatting and adds handlers as needed:
    1. StreamHandler for console output, if enabled.
    2. FileHandler for logging to a file, if log_file is specified.
    """
    handlers = []
    
    if stream_handler:
        # StreamHandler for console logging
        stream_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] - %(message)s', datefmt='%H:%M:%S')
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(stream_formatter)
        handlers.append(stream_handler)
        
    if log_file:
        file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s')
        file_handler = logging.FileHandler(log_file, mode='a')
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
        
    # Clear any previously added handlers from the root logger
    logging.getLogger().handlers = []
    
    # Set up the root logger configuration with the created handlers
    logging.basicConfig(level=level, handlers=handlers)

def close_root_logging():
    """
    Safely closes and removes all handlers associated with the root logger.

    This function should be called when you no longer need logging or before re-configuring
    logging. It is particularly useful for ensuring that FileHandlers release
    their file resources.

    Note that you typically do not need to manually close and remove handlers, 
    as Python's logging module will handle the cleanup when the program exits.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        handler.close()
        root_logger.removeHandler(handler)

def psychopy_log():
    """Returns a Path object for a log file in the log directory with a timestamped filename for the psychopy experiment"""
    log_dir = Path('log')
    log_dir.mkdir(parents=True, exist_ok=True)
    log_filename_str = datetime.now().strftime("%Y_%m_%d__%H_%M_%S") + ".log"
    log_file = log_dir / log_filename_str
    return log_file
