# bim_time

`bim_time.py` is a small Python script for fetching real-time departure information for Graz public transport from the HAFAS API at `verkehrsauskunft.verbundlinie.at`.

## Overview

The script provides functions to:

- Search for stops by name
- Find nearby stops by GPS coordinates
- Retrieve departure boards for a stop
- Format and display departure data in the console

## Functions

### `_hafas_request(svc_req: dict) -> dict`
Sends an HTTP POST request to the HAFAS API and returns the raw JSON response. It uses fixed client and authentication payload data.

### `suche_alle_haltestellen(name: str, max_treffer: int = 10) -> list[dict]`
Searches for stops matching the provided name and returns all matches.

Returns:
- A list of objects with `name`, `lid`, and `ext_id`
- An empty list if no matches are found

### `suche_haltestelle(name: str) -> str | None`
Searches for a stop and returns the `lid` of the first match.

Returns:
- `lid` of the first matching stop
- `None` if no stop is found

### `suche_haltestelle_koordinaten(lat: float, lon: float, radius_m: int = 500, max_treffer: int = 5) -> list[dict]`
Searches for stops within a radius around the given GPS coordinates.

Returns:
- A list of stops with `name`, `lid`, `ext_id`, and `distanz_m`
- Sorted by distance (nearest first)

### `Abfahrt`
A dataclass representing a single departure entry.

Fields:
- `linie`: Line number or name
- `typ`: Vehicle type (e.g. tram, city bus)
- `richtung`: Direction of travel
- `plan_zeit`: Scheduled departure time
- `echt_zeit`: Real-time departure time (if available)
- `countdown_min`: Minutes until departure
- `verspaetung_min`: Delay in minutes
- `status`: Status label (`pünktlich`, `verspätet`, `verfrüht`, `unbekannt`)
- `status_text`: Original status message from the API

### `_parse_zeit(time_str: str) -> datetime | None`
Parses a HAFAS time string (`HHMMSS` or `01HHMMSS`) into a `datetime` object in the Vienna timezone.

### `get_abfahrten(stop_lid: str, max_abfahrten: int = 10, filter_produkte: int = 4087) -> list[Abfahrt]`
Loads the next departures for a stop and returns them as a list of `Abfahrt` objects.

- `stop_lid`: HAFAS stop ID
- `max_abfahrten`: Maximum number of departures to return
- `filter_produkte`: Product filter value (default `4087` = all Graz Linien products)

### `print_abfahrtstafel(stop_lid: str, stop_name: str = "", max_abfahrten: int = 10)`
Prints a formatted departure board to the console.

- Uses `get_abfahrten()` to fetch data
- Displays line, direction, time, delay status, and countdown

## Examples
Representations of some use cases:

1. Directly display the departure board for a known stop (`Graz Steyrergasse`)
2. Search a stop by name (`Jakominiplatz`) and display departures
3. Print all matches for a search query (`Hauptplatz`)
4. Find nearby stops by GPS coordinates and display the nearest stop

```python
if __name__ == "__main__":

    # Example 1: Directly with a known lid
    STEYRERGASSE_LID = (
        "A=1@O=Graz Steyrergasse@X=15444313@Y=47061182@U=81@L=460406600@i=A×at:46:4066@"
    )
    print_abfahrtstafel(STEYRERGASSE_LID, stop_name="Graz Steyrergasse")

    # Example 2: Search by name, then fetch departures
    lid = suche_haltestelle("Jakominiplatz")
    if lid is None:
        print("Stop not found.")
    else:
        print_abfahrtstafel(lid, stop_name="Graz Jakominiplatz")

    # Example 3: Show all matches for a search query
    results = suche_alle_haltestellen("Hauptplatz", max_treffer=5)
    for r in results:
        print(f"{r['name']}  ->  {r['lid']}")

    # Example 4: Find the nearest stop by coordinates
    nearby = suche_haltestelle_koordinaten(lat=47.0670, lon=15.4421, radius_m=300)
    for r in nearby:
        print(f"{r['distanz_m']:>4}m  {r['name']}")

    if nearby:
        print_abfahrtstafel(nearby[0]["lid"], stop_name=nearby[0]["name"])
``` 

## Requirements

- Python 3.10+ (for `|` union types in function signatures)
- `requests` library

## Usage

```bash
python bim_time.py
```

To use the functions from another script:

```python
from bim_time import suche_haltestelle, get_abfahrten, print_abfahrtstafel

lid = suche_haltestelle("Jakominiplatz")
if lid:
    print_abfahrtstafel(lid, stop_name="Graz Jakominiplatz")
```

## Notes

This script uses the HAFAS API at `verkehrsauskunft.verbundlinie.at` and is designed for Graz Linien timetable data. Changes to the API or authentication may require updates.

## Thanks

Thanks to the team of [straba.at](https://straba.at/) for the great idea.
