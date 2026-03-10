import datetime as dt
import os

DEFAULT_PRICING_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
)
CACHE_PATH = os.path.expanduser("~/.cache/vibefetch/litellm_model_prices.json")
LOCAL_TZ = dt.datetime.now().astimezone().tzinfo
