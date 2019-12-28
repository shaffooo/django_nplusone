import logging

# to prevent an error message being output to sys.stderr in the absence of logging configuration
logging.getLogger('nplusone').addHandler(logging.NullHandler())

from base import show_nplusones
