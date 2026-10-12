"""
Converts a GTFS feed into a compact transit map for journey.py.

Usage: python prepare.py GTFS_ZIP OUTPUT_DIR [--date YYYYMMDD]

Writes three CSV files to OUTPUT_DIR:
- stations.csv: id, name, lat, lon (all platforms of a station joined)
- lines.csv: line, mode (metro/tram/bus/rail), color
- connections.csv: from, to, line, minutes (average travel time),
  km (average distance along the track, if the feed provides it)

Only trips on a reference date are considered: by default, the first Monday
in September within the feed period (in Vienna, the first school day).
Night lines, replacement services, and rarely served connections (short
detours) are left out. Timetables are only used to compute the travel times
and to tell regular from rare connections.
"""
import argparse
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# GTFS route types to modes
MODES = {0: 'tram', 1: 'metro', 2: 'rail', 3: 'bus'}
# lines whose GTFS route type does not match how they are usually seen
MODE_OVERRIDES = {'BB': 'rail'}  # Badner Bahn, a local railway to Baden
# month whose first Monday is the default reference date
REFERENCE_MONTH = 9
# minimum number of trips on the reference date for a line
MIN_TRIPS_PER_DAY = 1
# minimum share of a line's trips on the reference date (relative to its
# busiest connection on that date) for a connection
MIN_SHARE = 0.1

WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']


def read(feed: zipfile.ZipFile, name: str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(feed.open(name), encoding='utf-8-sig', dtype=str, **kwargs)


def station_ids(stops: pd.DataFrame) -> pd.Series:
    """
    Maps each stop (platform) id to a station id. Uses the parent station if
    given, otherwise the first three parts of a hierarchical stop id such as
    'at:49:657:0:3', otherwise the stop name.
    """
    if 'parent_station' in stops and stops.parent_station.notna().any():
        ids = stops.parent_station.fillna(stops.stop_id)
    elif stops.stop_id.str.count(':').min() >= 2:
        ids = stops.stop_id.str.split(':').str[:3].str.join(':')
    else:
        ids = stops.stop_name
    return pd.Series(ids.values, index=stops.stop_id)


def feed_period(calendar: pd.DataFrame, calendar_dates: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp]:
    """
    Returns the first and last day covered by the feed.
    """
    return (pd.Timestamp(min(calendar.start_date.min(), calendar_dates.date.min())),
            pd.Timestamp(max(calendar.end_date.max(), calendar_dates.date.max())))


def first_monday(month: int, first: pd.Timestamp, last: pd.Timestamp) -> pd.Timestamp:
    """
    Returns the first Monday in the given month between the given days.
    """
    for year in range(first.year, last.year + 1):
        start = pd.Timestamp(year=year, month=month, day=1)
        monday = start + pd.Timedelta(days=(7 - start.weekday()) % 7)
        if first <= monday <= last:
            return monday
    raise ValueError(f"feed period {first.date()} to {last.date()} has no first Monday in month {month}")


def services_on(calendar: pd.DataFrame, calendar_dates: pd.DataFrame, day: pd.Timestamp) -> set[str]:
    """
    Returns the ids of all services running on the given day.
    """
    date = day.strftime('%Y%m%d')
    regular = calendar[(calendar.start_date <= date) & (calendar.end_date >= date) &
                       (calendar[WEEKDAYS[day.weekday()]] == '1')].service_id
    exceptions = calendar_dates[calendar_dates.date == date]
    return ((set(regular) | set(exceptions[exceptions.exception_type == '1'].service_id))
            - set(exceptions[exceptions.exception_type == '2'].service_id))


def read_hops(feed: zipfile.ZipFile) -> pd.DataFrame:
    """
    Returns all hops between consecutive stops of all trips, with their
    travel time in seconds and distance in meters (NaN if not in the feed).
    """
    columns = ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence']
    has_distance = 'shape_dist_traveled' in pd.read_csv(feed.open('stop_times.txt'), nrows=0,
                                                        encoding='utf-8-sig').columns
    stop_times = pd.read_csv(feed.open('stop_times.txt'), encoding='utf-8-sig',
                             usecols=columns + ['shape_dist_traveled'] * has_distance,
                             dtype={'trip_id': 'category', 'arrival_time': 'category',
                                    'departure_time': 'category', 'stop_id': 'category',
                                    'stop_sequence': 'int32', 'shape_dist_traveled': 'float32'})

    def seconds(times: pd.Series):
        # convert via the categories, there are far fewer distinct times than rows
        hms = times.cat.categories.str.split(':', expand=True).to_frame().astype(int)
        lookup = (hms[0] * 3600 + hms[1] * 60 + hms[2]).to_numpy()
        return lookup[times.cat.codes.to_numpy()]

    # work on category codes rather than strings to save memory
    stop_times = stop_times.sort_values(['trip_id', 'stop_sequence'])
    trip = stop_times.trip_id.cat.codes.to_numpy()
    stop = stop_times.stop_id.cat.codes.to_numpy()
    arrival = seconds(stop_times.arrival_time)
    departure = seconds(stop_times.departure_time)
    distance = (stop_times.shape_dist_traveled.to_numpy() if has_distance
                else np.full(len(stop_times), np.nan, dtype='float32'))
    same_trip = trip[1:] == trip[:-1]
    trips = stop_times.trip_id.cat.categories
    stops = stop_times.stop_id.cat.categories
    return pd.DataFrame({'trip_id': pd.Categorical.from_codes(trip[:-1][same_trip], trips),
                         'from_stop': pd.Categorical.from_codes(stop[:-1][same_trip], stops),
                         'to_stop': pd.Categorical.from_codes(stop[1:][same_trip], stops),
                         'seconds': (arrival[1:] - departure[:-1])[same_trip],
                         'meters': (distance[1:] - distance[:-1])[same_trip]})


def lookup(column: pd.Series, mapping: pd.Series) -> np.ndarray:
    """
    Maps a categorical column through a mapping, looking up each category only once.
    """
    return mapping.reindex(column.cat.categories).to_numpy()[column.cat.codes.to_numpy()]


def prepare(gtfs_zip: Path, output_dir: Path, date: str | None = None):
    feed = zipfile.ZipFile(gtfs_zip)
    routes = read(feed, 'routes.txt')
    trips = read(feed, 'trips.txt', usecols=['route_id', 'service_id', 'trip_id'])
    stops = read(feed, 'stops.txt')
    calendar, calendar_dates = read(feed, 'calendar.txt'), read(feed, 'calendar_dates.txt')
    day = pd.Timestamp(date) if date else first_monday(REFERENCE_MONTH, *feed_period(calendar, calendar_dates))
    services = services_on(calendar, calendar_dates, day)
    print(f"reference date: {day.strftime('%A, %Y-%m-%d')} ({len(services)} services running)")

    # select lines
    routes['line'] = routes.route_short_name
    routes['mode'] = routes.route_type.astype(int).map(MODES)
    routes['mode'] = routes.line.map(MODE_OVERRIDES).fillna(routes['mode'])
    night = routes.line.str.match(r'N\d')
    replacement = routes.route_long_name.str.contains('ersatzverkehr', case=False, na=False)
    routes = routes[routes['mode'].notna() & ~night & ~replacement]
    print(f"{routes.line.nunique()} lines after removing night lines and replacement services")

    # collect hops between stations of trips running on the reference date
    print("reading stop times...")
    hops = read_hops(feed)
    trips = trips.merge(routes[['route_id', 'line']], on='route_id').set_index('trip_id')
    hops['line'] = lookup(hops.trip_id, trips.line)
    hops['running'] = lookup(hops.trip_id, trips.service_id.isin(services))
    station = station_ids(stops)
    hops['from'] = lookup(hops.from_stop, station)
    hops['to'] = lookup(hops.to_stop, station)
    hops = hops[hops.line.notna() & (hops['from'] != hops['to']) & hops.running.astype(bool)]

    # drop lines with very few trips
    trips_per_day = hops.drop_duplicates('trip_id').groupby('line').size()
    rare_lines = trips_per_day[trips_per_day < MIN_TRIPS_PER_DAY].index
    hops = hops[~hops.line.isin(rare_lines)]
    print(f"removed rare lines: {', '.join(sorted(rare_lines)) or 'none'}")

    # aggregate per connection, drop rarely served ones
    connections = hops.groupby(['from', 'to', 'line']).agg(
        trips=('trip_id', 'size'), seconds=('seconds', 'mean'), meters=('meters', 'mean')).reset_index()
    connections['minutes'] = (connections.seconds / 60).round(1)
    connections['km'] = (connections.meters / 1000).round(3)
    share = connections.trips / connections.groupby('line').trips.transform('max')
    print(f"removed {(share < MIN_SHARE).sum()} of {len(connections)} connections "
          f"served by less than {MIN_SHARE:.0%} of their line's trips")
    connections = connections[share >= MIN_SHARE]

    # stations: most common platform name, mean platform position
    stops['station'] = stops.stop_id.map(station)
    stops = stops[stops.station.isin(set(connections['from']) | set(connections['to']))]
    stations = stops.groupby('station').agg(
        name=('stop_name', lambda names: names.mode()[0]),
        lat=('stop_lat', lambda lat: lat.astype(float).mean()),
        lon=('stop_lon', lambda lon: lon.astype(float).mean())).reset_index()
    stations = stations.rename(columns={'station': 'id'}).sort_values('name')
    if stations.name.duplicated().any():
        print("warning: duplicate station names:",
              ', '.join(stations.name[stations.name.duplicated()]))

    # lines: mode and color as given by the most common route variant
    lines = (routes[routes.line.isin(set(connections.line))]
             .groupby('line').agg(mode=('mode', lambda m: m.mode()[0]),
                                  color=('route_color', lambda c: c.dropna().mode().get(0, '')))
             .reset_index())
    # sort by mode, then by line number (so 2 comes before 10), then by name
    lines['order'] = lines['mode'].map({'metro': 0, 'tram': 1, 'rail': 2, 'bus': 3})
    lines['number'] = lines.line.str.extract(r'(\d+)')[0].fillna(0).astype(int)
    lines = lines.sort_values(['order', 'number', 'line'])

    output_dir.mkdir(parents=True, exist_ok=True)
    stations[['id', 'name', 'lat', 'lon']].to_csv(output_dir / 'stations.csv', index=False,
                                                  float_format='%.6f')
    lines[['line', 'mode', 'color']].to_csv(output_dir / 'lines.csv', index=False)
    connections.sort_values(['line', 'from', 'to'])[['from', 'to', 'line', 'minutes', 'km']].to_csv(
        output_dir / 'connections.csv', index=False)
    print(f"wrote {len(stations)} stations, {len(lines)} lines, {len(connections)} connections "
          f"to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('gtfs_zip', type=Path, help="GTFS feed as a zip file")
    parser.add_argument('output_dir', type=Path, help="directory to write the CSV files to")
    parser.add_argument('--date', help="reference date as YYYYMMDD "
                        "(default: first Monday in September within the feed period)")
    args = parser.parse_args()
    prepare(args.gtfs_zip, args.output_dir, args.date)


if __name__ == '__main__':
    main()
