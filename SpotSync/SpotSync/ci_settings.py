"""Opt-in verification settings; never point these at a retained database."""

import os
from pathlib import Path

from .settings import *  # noqa: F403

# Require an explicit temporary destination instead of writing into tracked media.
_output_dir = Path(os.environ['SPOTSYNC_CI_OUTPUT_DIR']).resolve()
MEDIA_ROOT = _output_dir / 'media'
STATIC_ROOT = _output_dir / 'staticfiles'
DEBUG = True
GOOGLE_MAPS_API_KEY = ''
GOOGLE_MAPS_BROWSER_API_KEY = ''
