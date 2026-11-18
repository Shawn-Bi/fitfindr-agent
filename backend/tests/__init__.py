"""
Unit tests never reach RapidAPI: the key is blanked before config loads .env
(python-dotenv doesn't override a variable that is already set), so even a
test that forgets to patch an adapter fails instead of spending quota.
"""

import os

os.environ["RAPIDAPI_KEY"] = ""
