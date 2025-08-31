# -*- coding: utf-8 -*-
import os
import logging

_logger = logging.getLogger(__name__)

def post_init_hook(env):
    """Called after module installation"""
    _logger.info("Inouk Cloudflare Long Polling Patch installed - timeouts adjusted for 30s limit")

# Apply monkey patch on module load
from . import cloudflare_patch