import logging


def get_logger(name):
    formatter = logging.Formatter(
        '%(asctime)s %(name)s %(levelname)s: %(message)s',
        '%m/%d/%Y %H:%M:%S'
    )
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()

    file_handler = logging.FileHandler("log.log")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    return logger
