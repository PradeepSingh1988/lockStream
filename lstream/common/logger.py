import logging


class CustomAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return "[%s] %s" % (self.extra["logger"], msg), kwargs


def setup_logger():
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    if not logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    return logger
