"""Primary configuration now delegated to config_new.
Import this module everywhere (backwards compatible) while allowing
config_new.py to be the single source of truth for parameter values.
"""
from config_new import *  # noqa: F401,F403

# Legacy-only constants retained for compatibility (define if missing)
BACKTEST_MAX_RETRIES = globals().get('BACKTEST_MAX_RETRIES', 2)
BACKTEST_RETRY_DELAY_SEC = globals().get('BACKTEST_RETRY_DELAY_SEC', 30)
