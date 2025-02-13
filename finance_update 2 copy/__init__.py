"""Package initialization and logging configuration."""

import logging
import sys

# Configure root logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Create console handler with DEBUG level
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)

# Create formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add console handler to root logger
logger.addHandler(console_handler)
