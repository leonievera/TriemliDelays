from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any

from config import API_URL, STOP_ID


def fetch_stationboard() -> dict[str, Any]:
    params = urllib.parse.urlencode(
        {
            "stop": STOP_ID,
            "mode": "depart",
            "limit": 0,
            "show_delays": 1,
            "transportation_types": "tram",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{params}")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
