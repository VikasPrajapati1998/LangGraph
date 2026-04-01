import requests
import ntplib
from datetime import datetime, timezone, timedelta


def _convert_to_ist(dt_utc):
    IST = timezone(timedelta(hours=5, minutes=30))
    return dt_utc.astimezone(IST)


def get_current_datetime(return_ist=True):
    """
    Returns current datetime.
    
    Priority:
    1. NTP (internet)
    2. HTTP API (internet)
    3. System time (fallback)

    Args:
        return_ist (bool): If True → returns IST, else UTC

    Returns:
        datetime object (always)
    """

    # 1️⃣ NTP
    ntp_servers = [
        "pool.ntp.org",
        "time.google.com",
        "time.windows.com"
    ]

    for server in ntp_servers:
        try:
            client = ntplib.NTPClient()
            response = client.request(server, version=3, timeout=3)

            dt_utc = datetime.fromtimestamp(response.tx_time, timezone.utc)
            return _convert_to_ist(dt_utc) if return_ist else dt_utc

        except Exception:
            continue  # silent fail

    # 2️⃣ HTTP APIs
    urls = [
        "https://worldtimeapi.org/api/ip",
        "https://timeapi.io/api/Time/current/zone?timeZone=UTC"
    ]

    for url in urls:
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()

            if "utc_datetime" in data:
                dt_utc = datetime.fromisoformat(data["utc_datetime"].replace("Z", "+00:00"))

            elif "dateTime" in data:
                dt_utc = datetime.fromisoformat(data["dateTime"])

            else:
                continue

            return _convert_to_ist(dt_utc) if return_ist else dt_utc

        except Exception:
            continue

    # 3️⃣ Fallback → System time
    local_time = datetime.now(timezone.utc)
    return _convert_to_ist(local_time) if return_ist else local_time




# current_time = get_current_datetime()
# print(current_time)

# # If you want UTC instead of IST
# utc_time = get_current_datetime(return_ist=False)
# print(utc_time)
