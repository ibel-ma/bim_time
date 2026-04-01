"""
Graz departure board
Fetches real-time departures from the HAFAS API (verkehrsauskunft.verbundlinie.at).

Usage:
    # Search for a stop by name
    lid = suche_haltestelle("Steyrergasse")
    lid = suche_haltestelle("Jakominiplatz")   # returns the first match

    # Search for all matches
    results = suche_alle_haltestellen("Jakominiplatz")

    # Search by coordinates
    results = suche_haltestelle_koordinaten(lat=47.0670, lon=15.4421)

    # Fetch departures
    departures = get_abfahrten(lid)
    print_abfahrtstafel(lid, stop_name="Graz Steyrergasse")
"""

import time
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
import os
import platform


# ── HAFAS base configuration ──────────────────────────────────────────────────

_HAFAS_URL = "https://verkehrsauskunft.verbundlinie.at/hamm/gate"
_HAFAS_AUTH = {"type": "AID", "aid": "wf7mcf9bv3nv8g5f"}
_HAFAS_CLIENT = {"id": "VAO", "type": "WEB", "name": "webapp", "l": "vs_stv", "v": 10010}
_HAFAS_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": "https://verkehrsauskunft.verbundlinie.at",
    "Referer": "https://verkehrsauskunft.verbundlinie.at/webapp/index.html?L=vs_stv",
}


def _hafas_request(svc_req: dict) -> dict:
    """Sends a HAFAS request and returns the raw JSON response."""
    url = f"{_HAFAS_URL}?rnd={int(time.time() * 1000)}"
    payload = {
        "id": "request01",
        "ver": "1.59",
        "lang": "deu",
        "auth": _HAFAS_AUTH,
        "client": _HAFAS_CLIENT,
        "ext": "VAO.22",
        "formatted": False,
        "svcReqL": [svc_req],
    }
    resp = requests.post(url, json=payload, headers=_HAFAS_HEADERS, timeout=10)
    resp.raise_for_status()
    return resp.json()


# ── Stop search ───────────────────────────────────────────────────────────────

def suche_alle_haltestellen(name: str, max_treffer: int = 10) -> list[dict]:
    """
    Searches for stops by name and returns all matches.

    Args:
        name:        Search string (e.g. "Steyrergasse", "Jakominiplatz")
        max_treffer: Maximum number of results to return

    Returns:
        List of dicts with keys: "name", "lid", "ext_id"
        Empty list if nothing found.

    Raises:
        requests.RequestException: On network or HTTP errors
        ValueError: On empty search string or HAFAS error
    """
    if not name or not name.strip():
        raise ValueError("Search string must not be empty.")

    data = _hafas_request({
        "meth": "LocMatch",
        "id": "1|1|",
        "req": {
            "input": {
                "loc": {"type": "S", "name": name.strip()},
                "maxLoc": max_treffer,
                "field": "S",
            }
        },
    })

    svc_res = data.get("svcResL", [{}])[0]
    if svc_res.get("err", "OK") != "OK":
        raise ValueError(f"HAFAS error: {svc_res.get('err')}")

    matches = svc_res.get("res", {}).get("match", {}).get("locL", [])

    results = []
    for loc in matches:
        lid = loc.get("lid", "")
        stop_name = loc.get("name", "")
        ext_id = loc.get("extId", "")
        if lid and stop_name:
            results.append({"name": stop_name, "lid": lid, "ext_id": ext_id})

    return results


def suche_haltestelle(name: str) -> str | None:
    """
    Searches for a stop and returns the lid of the first match.

    Args:
        name: Search string (e.g. "Steyrergasse", "Jakominiplatz")

    Returns:
        lid string of the first match, or None if nothing found.

    Raises:
        requests.RequestException: On network or HTTP errors
        ValueError: On empty search string or HAFAS error

    Example:
        lid = suche_haltestelle("Steyrergasse")
        if lid is None:
            print("Stop not found.")
        else:
            departures = get_abfahrten(lid)
    """
    results = suche_alle_haltestellen(name, max_treffer=1)
    if not results:
        return None
    return results[0]["lid"]


def suche_haltestelle_koordinaten(
    lat: float,
    lon: float,
    radius_m: int = 500,
    max_treffer: int = 5,
) -> list[dict]:
    """
    Finds stops near a GPS coordinate.

    HAFAS expects coordinates as integers (degrees * 1_000_000).

    Args:
        lat:         Latitude  (e.g. 47.0612)
        lon:         Longitude (e.g. 15.4444)
        radius_m:    Search radius in metres (default: 500)
        max_treffer: Maximum number of stops to return

    Returns:
        List of dicts with keys: "name", "lid", "ext_id", "distanz_m"
        Sorted by distance (nearest first).
        Empty list if nothing found.

    Raises:
        requests.RequestException: On network or HTTP errors
        ValueError: On HAFAS error

    Example:
        # Nearest stop to Jakominiplatz
        results = suche_haltestelle_koordinaten(47.0670, 15.4421)
        lid = results[0]["lid"]
    """
    data = _hafas_request({
        "meth": "LocGeoPos",
        "id": "1|1|",
        "req": {
            "ring": {
                "cCrd": {
                    "x": int(lon * 1_000_000),
                    "y": int(lat * 1_000_000),
                },
                "maxDist": radius_m,
            },
            "getPOIs": False,
            "getStops": True,
            "maxLoc": max_treffer,
        },
    })

    svc_res = data.get("svcResL", [{}])[0]
    if svc_res.get("err", "OK") != "OK":
        raise ValueError(f"HAFAS error: {svc_res.get('err')}")

    matches = svc_res.get("res", {}).get("locL", [])

    results = []
    for loc in matches:
        lid = loc.get("lid", "")
        stop_name = loc.get("name", "")
        ext_id = loc.get("extId", "")
        distance = loc.get("dist", -1)
        if lid and stop_name:
            results.append({
                "name": stop_name,
                "lid": lid,
                "ext_id": ext_id,
                "distanz_m": distance,
            })

    return results


# ── Departure data ────────────────────────────────────────────────────────────

@dataclass
class Abfahrt:
    linie: str          # e.g. "5", "4", "N5"
    typ: str            # e.g. "Straßenbahn", "Stadtbus", "Nachtbus"
    richtung: str       # e.g. "Andritz", "Puntigam"
    plan_zeit: str      # e.g. "20:35"
    echt_zeit: str      # e.g. "20:34" (empty if no real-time data available)
    countdown_min: int  # minutes until departure (based on real-time if available)
    verspaetung_min: int  # positive = delayed, negative = early, 0 = on time
    status: str         # "pünktlich", "verspätet", "verfrüht", "unbekannt"
    status_text: str    # original status message from the API

    def __str__(self):
        time_str = self.echt_zeit if self.echt_zeit else self.plan_zeit
        countdown = f"{self.countdown_min} min" if self.countdown_min >= 0 else "now"
        delay = ""
        if self.verspaetung_min > 0:
            delay = f" (+{self.verspaetung_min} min)"
        elif self.verspaetung_min < 0:
            delay = f" ({self.verspaetung_min} min)"
        return f"{self.typ} {self.linie:>3}  ->  {self.richtung:<30}  {time_str}{delay}  [{countdown}]"


def _parse_zeit(time_str: str) -> datetime | None:
    """
    Parses a HAFAS time string into a datetime object (today, Vienna timezone).
    HAFAS format: "HHMMSS" or "01HHMMSS" (next day).
    TODO: Handle Error with times after midnight.
    """
    if not time_str:
        return None

    vienna = ZoneInfo("Europe/Vienna")  # CEST; use timedelta(hours=1) for CET
    today = datetime.now(vienna).date()

    next_day = False
    if time_str.startswith("01"):
        next_day = True
        time_str = time_str[2:]

    h = int(time_str[0:2])
    m = int(time_str[2:4])
    s = int(time_str[4:6]) if len(time_str) >= 6 else 0

    dt = datetime(today.year, today.month, today.day, h, m, s, tzinfo=vienna)
    if next_day:
        dt += timedelta(days=1)
    return dt


def get_abfahrten(
    stop_lid: str,
    max_abfahrten: int = 10,
    filter_produkte: int = 4087,  # 4087 = all Graz Linien products
) -> list[Abfahrt]:
    """
    Returns the next departures for a given stop.

    Args:
        stop_lid:        HAFAS stop ID (lid format)
        max_abfahrten:   Maximum number of departures to return
        filter_produkte: Product filter value (4087 = all local lines)

    Returns:
        List of Abfahrt objects, sorted by departure time
    """
    data = _hafas_request({
        "meth": "StationBoard",
        "id": "1|1|",
        "req": {
            "stbLoc": {"lid": stop_lid},
            "jnyFltrL": [{"type": "PROD", "mode": "INC", "value": filter_produkte}],
            "type": "DEP",
            "sort": "PT",
            "maxJny": max_abfahrten,
        },
    })

    # Navigate to the result list
    res = data["svcResL"][0]["res"]
    common = res["common"]
    journeys = res.get("jnyL", [])
    product_list = common.get("prodL", [])

    vienna = ZoneInfo("Europe/Vienna")  # CEST; use timedelta(hours=1) for CET
    now = datetime.now(vienna)

    departures = []

    for journey in journeys:
        stb = journey.get("stbStop", {})

        # Scheduled time
        planned_str = stb.get("dTimeS", "")
        planned_dt = _parse_zeit(planned_str)
        if not planned_dt:
            continue
        plan_zeit = planned_dt.strftime("%H:%M")

        # Real-time
        realtime_str = stb.get("dTimeR", "")
        realtime_dt = _parse_zeit(realtime_str)
        echt_zeit = realtime_dt.strftime("%H:%M") if realtime_dt else ""

        # Countdown — prefer real-time over scheduled
        departure_dt = realtime_dt if realtime_dt else planned_dt
        countdown_sec = (departure_dt - now).total_seconds()
        countdown_min = max(0, int(countdown_sec / 60))

        # Delay in minutes
        if realtime_dt and planned_dt:
            verspaetung_min = int((realtime_dt - planned_dt).total_seconds() / 60)
        else:
            verspaetung_min = 0

        # Status
        prog_type = stb.get("dProgType", "")
        fr_text = stb.get("dTimeFR", {}).get("txtA", "")
        if prog_type == "PROGNOSED":
            if verspaetung_min == 0:
                status = "pünktlich"
            elif verspaetung_min > 0:
                status = "verspätet"
            else:
                status = "verfrüht"
        else:
            status = "unbekannt"

        # Line name and type from the shared product list
        prod_idx = journey.get("prodX")
        linie = "?"
        typ = "?"
        if prod_idx is not None and prod_idx < len(product_list):
            prod = product_list[prod_idx]
            linie = prod.get("nameS") or prod.get("name", "?")
            ctx = prod.get("prodCtx", {})
            typ = ctx.get("catOutL", prod.get("name", "?"))

        richtung = journey.get("dirTxt", "?")

        departures.append(
            Abfahrt(
                linie=linie,
                typ=typ,
                richtung=richtung,
                plan_zeit=plan_zeit,
                echt_zeit=echt_zeit,
                countdown_min=countdown_min,
                verspaetung_min=verspaetung_min,
                status=status,
                status_text=fr_text,
            )
        )

    return departures


def print_abfahrtstafel(stop_lid: str, stop_name: str = "", max_abfahrten: int = 10):
    """Prints a formatted departure board to the console."""
    departures = get_abfahrten(stop_lid, max_abfahrten=max_abfahrten)

    title = stop_name or "Departure board"
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"  As of: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*65}")
    print(f"  {'Line':<12} {'Direction':<30} {'Time':<8} {'Status'}")
    print(f"{'-'*65}")

    for a in departures:
        time_str = a.echt_zeit if a.echt_zeit else a.plan_zeit
        delay = ""
        if a.verspaetung_min > 0:
            delay = f"(+{a.verspaetung_min}')"
        elif a.verspaetung_min < 0:
            delay = f"({a.verspaetung_min}')"

        countdown = f"{a.countdown_min} min" if a.countdown_min > 0 else "now"
        print(
            f"  {a.typ} {a.linie:<5}  {a.richtung:<30} {time_str} {delay:<7} [{countdown}]"
        )

    print(f"{'='*65}\n")


def print_abfahrtstafel_minimal(stop_lid: str, stop_name: str = "", max_abfahrten: int = 10):
    """Prints a formatted departure board to the console."""
    # TODO: implement filter, line, direction
    departures = get_abfahrten(stop_lid, max_abfahrten=max_abfahrten)

    title = stop_name or "Departure board"
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"  As of: {datetime.now().strftime('%H:%M:%S')}")
    print(f"{'='*55}")
    print(f"  {'Line':<12} {'Direction':<30} {'Minutes':<8}")
    print(f"{'-'*55}")

    # set can only store unique values, check is fast
    output = set()

    # filter depature list
    filters = {
        "richtung": "Liebenau",
    }
    departures = filter_departures(departures, filters)

    for a in departures:
        #if (a.linie, a.richtung) not in output:
        print(
            f"  {a.linie:<11}  {a.richtung:<30} {a.countdown_min}"
        )
        output.add((a.linie, a.richtung))

    print(f"{'='*55}\n")


def filter_departures(departures, filters=None):
    """
    Optimized function to filter the list of Abfahrt objects using a dictionary of criteria.

    Args:
        departures (list): List of Abfahrt objects.
        filters (dict, optional): Dictionary of filter criteria.
            Example: {"line": "U3", "direction": "Ottakring", "status": "on_time"}

    Returns:
        list: Filtered list of Abfahrt objects.
    """
    if not filters:
        return departures

    return [
        departure
        for departure in departures
        if all(
            (getattr(departure, key) == value)
            for key, value in filters.items()
        )
    ]

def clear_terminal():
    """Clears the terminal screen."""
    if platform.system() == "Windows":
        os.system('cls')
    else:
        os.system('clear')

def update_display(departures: list, stop_name: str = "", max_abfahrten: int = 10, last_update_time=None, filters=None):
    """Prints a formatted departure board to the console."""
    clear_terminal()

    # calc minutes from last update
    current_time = time.time()
    countdown_seconds = current_time - last_update_time
    countdown_minutes = max(0, int(countdown_seconds / 60))

    title = stop_name or "Departure board"
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(
    f"  As of: {datetime.now().strftime('%H:%M:%S')} {' '*15}"
    f"{'Last update: ' if (last_update_time and countdown_minutes > 0) else f'{' '*13}'}"
    f"{f'({countdown_minutes} min)' if (last_update_time and countdown_minutes > 0) else 'N/A'}"
        )
    print(f"{'='*55}")
    print(f"  {'Line':<12} {'Direction':<30} {'Minutes':<8}")
    print(f"{'-'*55}")

    # filter depature list
    departures = filter_departures(departures, filters)

    for a in departures:
        print(
            f"  {a.linie:<11}  {a.richtung:<30} {a.countdown_min}"
        )
    print(f"{'='*55}")
    print(f"  exit process with ctrl+c\n")

def bim_monitor(stop_lid: str, stop_name: str = "", max_abfahrten: int = 10, filters=None):
    # Initial fetch
    departures = get_abfahrten(stop_lid, max_abfahrten)
    last_request_time = time.time()
    # filter before update display
    # TODO: filter before departure list is generated, to reduce the amount of data to process
    # TODO: filter for countdown_min < 0 to remove already departed lines
    # filter depature list
    departures = filter_departures(departures, filters)

    # update display with initial data
    update_display(departures, stop_name, last_update_time=last_request_time)

    # wrap in try-except to allow graceful exit on ctrl+c
    try:
        while True:
            current_time = time.time()

            # wait a minute
            time.sleep(60)
            # Decrement the value for countdown_min
            for obj in departures:
                obj.countdown_min -= 1
            # remove already departed lines (countdown_min < 0)
            departures = [obj for obj in departures if obj.countdown_min >= 0]
            # update display
            update_display(departures, stop_name, last_update_time=last_request_time)

            # after 5 minutes, fetch new data from API
            if current_time - last_request_time >= 300:
                departures = get_abfahrten(stop_lid, max_abfahrten)
                last_request_time = current_time
                # filter depature list
                departures = filter_departures(departures, filters)
    except KeyboardInterrupt:
        clear_terminal()
        print("\nMonitoring stopped by user. Exiting gracefully...")
        # Add cleanup code here if needed


# ── Examples ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    STEYRERGASSE_LID = (
        "A=1@O=Graz Steyrergasse@X=15444313@Y=47061182@U=81@L=460406600@i=A×at:46:4066@"
    )
    bim_monitor(STEYRERGASSE_LID, stop_name="Graz Steyrergasse", filters={"richtung": "Liebenau"})