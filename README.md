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

### `suche_haltestellen(name: str, max_treffer: int = 10) -> list[dict]`
Searches for stops matching the provided name and returns all matches.

Returns:
- A list of objects with `name`, `lid`, and `ext_id`
- An empty list if no matches are found

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

### `print_abfahrtstafel(departures: list, stop_name: str = "", max_abfahrten: int = 10, last_update_time = None)`
Prints a formatted departure board to the console.

- Uses `get_abfahrten()` to fetch data
- Displays line, direction, time, delay status, and countdown

### àrgv`: Arguments
```python

```

## Examples
Representations of some use cases:

1. Directly display the departure board for a known stop (`Graz Steyrergasse`)
2. Search a stop by name (`Jakominiplatz`) and display departures
3. Print all matches for a search query (`Hauptplatz`)
4. Find nearby stops by GPS coordinates and display the nearest stop

```python

``` 

## Requirements

- Python 3.10+ (for `|` union types in function signatures)
- `requests` library
- `datetime` library

## Usage

```bash
python bim_time.py
```

```
===========================================================================
 Steyrergasse
 As of: 01:03                                          Last update: 0 min
===========================================================================
 Line                Direction                              Time     Status
---------------------------------------------------------------------------
 Straßenbahn  4      Liebenau                               (04:53)  [229]
 Straßenbahn  4      Liebenau                               (05:03)  [239]
 Straßenbahn  4      Liebenau                               (05:23)  [259]
===========================================================================
Running... Press Ctrl+C to stop.
```

## Notes

This script uses the HAFAS API at `verkehrsauskunft.verbundlinie.at` and is designed for Graz Linien timetable data. Changes to the API or authentication may require updates.

## Thanks

Thanks Melissa for the great idea.
Also thanks to the team of [straba.at](https://straba.at/) for the inspiration.
