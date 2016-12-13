import logging
import logging.handlers
import constants

def initialize_logger(log_file_name):
    log_format = '%(levelname)s %(asctime)s [%(filename)s %(funcName)s %(lineno)d]: %(message)s'
    formatter = logging.Formatter(log_format)
    logger = logging.getLogger(log_file_name)
    filehandler = logging.handlers.RotatingFileHandler(
              log_file_name, maxBytes=10000000, backupCount=5)
    filehandler.setFormatter(formatter)
    logger.setLevel(logging.INFO)
    logger.addHandler(filehandler)
    return logger


LOG = None
def get_logger():
    global LOG
    if not LOG:
        LOG = initialize_logger(constants.LOG_FILENAME)
    return LOG    
