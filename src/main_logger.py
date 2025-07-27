import logging
import sys


logger = logging.getLogger("main logger")
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] [%(message)s]",
    datefmt="%d-%m-%y %H:%M:%S"
)


console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)


if not logger.handlers:
    logger.addHandler(console_handler)

logger.propagate = False
