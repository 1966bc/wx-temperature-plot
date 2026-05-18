# fetch_temperatures.py
# -*- coding: utf-8 -*-

"""
Fetch monthly temperature climatology from Open-Meteo and write the JSON
file consumed by sample_two.py.

Data source: Open-Meteo Historical Weather API (CC BY 4.0)
             https://open-meteo.com/en/docs/historical-weather-api

Usage:
    python3 fetch_temperatures.py [city] [years_back]

Defaults:
    city       = Rome
    years_back = 10

Examples:
    python3 fetch_temperatures.py
    python3 fetch_temperatures.py Reykjavik
    python3 fetch_temperatures.py "New York" 5
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(HERE, "temperatures.json")

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

DEFAULT_CITY = "Rome"
DEFAULT_YEARS_BACK = 10

# Open-Meteo archive lags real time by a few days. Use last complete year as end.
END_YEAR_OFFSET = 1

HTTP_TIMEOUT = 30

# ---------------------------------------------------------------------------


def http_get_json(url, params):
    """Make a GET request, return parsed JSON dict or None on error."""

    query = urllib.parse.urlencode(params)
    full_url = "%s?%s" % (url, query)

    try:
        with urllib.request.urlopen(full_url, timeout=HTTP_TIMEOUT) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as err:
        sys.stderr.write("HTTP error on %s: %s\n" % (full_url, err))
        return None


def geocode_city(name):
    """Resolve city name to (latitude, longitude, canonical_name). None on error."""

    data = http_get_json(GEOCODE_URL, {
        "name": name,
        "count": 1,
        "language": "en",
        "format": "json",
    })

    if data is None:
        return None

    results = data.get("results")
    if not results:
        sys.stderr.write("city not found: %s\n" % name)
        return None

    first = results[0]
    return (first["latitude"], first["longitude"], first["name"])


def fetch_archive(latitude, longitude, start_date, end_date):
    """Fetch daily min/max temperatures from Open-Meteo. None on error."""

    return http_get_json(ARCHIVE_URL, {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "temperature_2m_min,temperature_2m_max",
        "timezone": "auto",
    })


def aggregate_monthly(times, values):
    """Aggregate a daily series to (means, stddevs). Each is a list of 12 floats."""

    buckets = []
    for i in range(12):
        buckets.append([])

    # First pass: bucket values by month, skip nulls.
    for i in range(len(times)):
        month_index = int(times[i][5:7]) - 1
        value = values[i]
        if value is None:
            continue
        buckets[month_index].append(value)

    means = []
    stddevs = []

    for bucket in buckets:
        if len(bucket) == 0:
            means.append(None)
            stddevs.append(None)
            continue

        n = len(bucket)
        mean = sum(bucket) / n
        means.append(round(mean, 1))

        if n < 2:
            stddevs.append(0.0)
            continue

        # Sample stddev with Bessel correction (n - 1).
        squared_dev_sum = 0.0
        for value in bucket:
            squared_dev_sum = squared_dev_sum + (value - mean) ** 2
        variance = squared_dev_sum / (n - 1)
        stddevs.append(round(variance ** 0.5, 2))

    return (means, stddevs)


def build_payload(city_name, min_data, max_data):
    """Assemble the JSON structure consumed by sample_two.py."""

    min_means, min_stddevs = min_data
    max_means, max_stddevs = max_data

    return {
        "title": "Average temperature graph for %s" % city_name,
        "labels": {"x": "Months", "y": "Temperatures"},
        "months": MONTH_NAMES,
        "series": [
            {
                "legend": "Lowest",
                "colour": "blue",
                "marker": "triangle_down",
                "values": min_means,
                "stddev": min_stddevs,
            },
            {
                "legend": "Maximum",
                "colour": "orange",
                "marker": "triangle",
                "values": max_means,
                "stddev": max_stddevs,
            },
        ],
    }


def write_json(path, payload):
    """Write payload to disk. Return 0 on success, 1 on error."""

    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=4, ensure_ascii=False)
        return 0
    except OSError as err:
        sys.stderr.write("cannot write %s: %s\n" % (path, err))
        return 1


# ---------------------------------------------------------------------------

def parse_args(argv):
    """Read city and years_back from CLI. Return tuple or None on parse error."""

    city = DEFAULT_CITY
    years_back = DEFAULT_YEARS_BACK

    if len(argv) >= 2:
        city = argv[1]
    if len(argv) >= 3:
        try:
            years_back = int(argv[2])
        except ValueError:
            sys.stderr.write("invalid years_back: %s\n" % argv[2])
            return None

    return (city, years_back)


def main(argv):
    args = parse_args(argv)
    if args is None:
        return 1

    city, years_back = args

    sys.stderr.write("geocoding %s...\n" % city)
    geo = geocode_city(city)
    if geo is None:
        return 1

    latitude, longitude, city_name = geo
    sys.stderr.write("found %s at lat=%s lon=%s\n" % (city_name, latitude, longitude))

    current_year = datetime.date.today().year
    end_year = current_year - END_YEAR_OFFSET
    start_year = end_year - years_back + 1
    start_date = "%d-01-01" % start_year
    end_date = "%d-12-31" % end_year

    sys.stderr.write("fetching %s to %s\n" % (start_date, end_date))
    archive = fetch_archive(latitude, longitude, start_date, end_date)
    if archive is None:
        return 1

    daily = archive.get("daily")
    if daily is None:
        sys.stderr.write("no daily section in response\n")
        return 1

    times = daily["time"]
    mins = aggregate_monthly(times, daily["temperature_2m_min"])
    maxs = aggregate_monthly(times, daily["temperature_2m_max"])

    payload = build_payload(city_name, mins, maxs)
    result = write_json(OUTPUT_FILE, payload)

    if result == 0:
        sys.stderr.write("wrote %s\n" % OUTPUT_FILE)
    return result


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main(sys.argv))
