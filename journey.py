"""
Journey planning in a public transit network as a search problem.

A state is a stop, an action rides a line to a neighboring stop. Timetables
are ignored. The map data is prepared from GTFS feeds by maps/prepare.py.
"""
import csv
from dataclasses import dataclass
from difflib import get_close_matches
from html import escape
from math import asin, cos, isnan, radians, sin, sqrt
from pathlib import Path
from typing import Iterable

from drawing import draw_search_tree, show_svg, svg_document

MAPS_DIR = Path(__file__).parent / 'maps'
EARTH_RADIUS_KM = 6371.0

# all modes of transport, in the order lines are listed and drawn on top of each other
MODES = ('metro', 'tram', 'rail', 'bus')


@dataclass(frozen=True)
class Line:
    """
    A transit line, such as 'U1' (metro), 'D' (tram), or '13A' (bus).
    """
    name: str
    mode: str
    color: str  # as a hex code, e.g., '#E3000F'

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class JourneyState:
    """
    Being at a stop, given by its name and location.
    """
    stop: str
    lat: float
    lon: float

    def __str__(self) -> str:
        return self.stop


@dataclass(frozen=True)
class JourneyAction:
    """
    Riding a line to the next stop, at a cost depending on the problem
    (1 per stop, minutes, or kilometers).
    """
    line: Line
    stop: str
    cost: float = 1

    def __str__(self) -> str:
        return f"take {self.line} to {self.stop}"


@dataclass(frozen=True)
class Connection:
    """
    A ride on a line to the next stop, with its typical duration and length.
    """
    line: Line
    stop: str
    minutes: float
    km: float


# ways to compute the cost of riding a connection
COSTS = {'stops': lambda connection: 1,
         'time': lambda connection: connection.minutes,
         'distance': lambda connection: connection.km}


class TransitMap:
    """
    A transit network of stops connected by lines.
    """
    def __init__(self, name: str, stops: dict[str, JourneyState], lines: dict[str, Line],
                 connections: dict[str, list[Connection]]):
        self.name = name
        self.stops = stops                # stop name -> state
        self.lines = lines                # line name -> line
        self.connections = connections    # stop name -> connections to next stops

    def get_stop(self, name: str) -> JourneyState:
        """
        Returns the state for the stop of the given name.
        """
        try:
            return self.stops[name]
        except KeyError:
            suggestions = get_close_matches(name, self.stops, n=3)
            hint = f" Did you mean {' or '.join(map(repr, suggestions))}?" if suggestions else ""
            raise KeyError(f"no stop named {name!r} on this map.{hint}") from None

    def search_route(self, start: str, goal: str, cost: str = 'stops') -> 'JourneyProblem':
        """
        Returns the problem of traveling from one stop to another. The cost of
        each ride to the next stop is 1 for cost='stops', the typical travel
        time in minutes for cost='time', or the distance along the track in
        kilometers for cost='distance'.
        """
        if cost not in COSTS:
            raise ValueError(f"unknown cost {cost!r}, expected one of {list(COSTS)}")
        return JourneyProblem(self, self.get_stop(start), self.get_stop(goal), cost)

    def __repr__(self) -> str:
        num_connections = sum(len(c) for c in self.connections.values())
        return (f"<TransitMap {self.name}: {len(self.stops)} stops, {len(self.lines)} lines, "
                f"{num_connections} connections>")


class JourneyProblem:
    """
    The state space of traveling from a start stop to a goal stop.
    """
    def __init__(self, transit_map: TransitMap, start: JourneyState, goal: JourneyState,
                 cost: str = 'stops'):
        self.map = transit_map
        self.start = start
        self.goal = goal
        self.cost = cost

    def get_start(self) -> JourneyState:
        return self.start

    def is_goal(self, state: JourneyState) -> bool:
        return state == self.goal

    def successors(self, state: JourneyState) -> list[tuple[JourneyAction, JourneyState]]:
        """
        Returns all stops reachable by riding a line for one stop, ordered by
        line (as listed in the map) and then by stop name.
        """
        cost = COSTS[self.cost]
        return [(JourneyAction(connection.line, connection.stop, cost(connection)),
                 self.map.stops[connection.stop])
                for connection in self.map.connections[state.stop]]


def load_map(city: str, restrict: list[str] | None = None) -> TransitMap:
    """
    Loads the transit map of a city from maps/<city>/. If `restrict` is given,
    only lines of the listed modes are included (any of 'metro', 'tram',
    'rail', 'bus'), along with the stops they serve.
    """
    directory = MAPS_DIR / city
    if not directory.is_dir():
        available = sorted(d.name for d in MAPS_DIR.iterdir() if (d / 'stations.csv').exists())
        raise ValueError(f"no map for {city!r}, available: {', '.join(available)}")
    modes = MODES if restrict is None else restrict
    if unknown := set(modes) - set(MODES):
        raise ValueError(f"unknown modes {sorted(unknown)}, expected some of {list(MODES)}")

    def read(name: str) -> list[dict[str, str]]:
        with open(directory / name, newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))

    lines = {row['line']: Line(row['line'], row['mode'], f"#{row['color']}" if row['color'] else '#888888')
             for row in read('lines.csv') if row['mode'] in modes}
    stations = {row['id']: JourneyState(row['name'], float(row['lat']), float(row['lon']))
                for row in read('stations.csv')}
    connections = {}
    for row in read('connections.csv'):
        if row['line'] in lines:
            origin, destination = stations[row['from']], stations[row['to']]
            # the track can never be shorter than the straight line between the stops (as
            # placed on the map), so straight-line distances are valid A* heuristics
            km = float(row.get('km') or 'nan')
            straight = straight_line_km(origin, destination)
            km = straight if isnan(km) else max(km, straight)
            connections.setdefault(origin.stop, []).append(Connection(
                lines[row['line']], destination.stop, float(row['minutes']), km))
            connections.setdefault(destination.stop, [])

    # order connections by line (as in lines.csv) and destination name
    line_order = {name: i for i, name in enumerate(lines)}
    for options in connections.values():
        options.sort(key=lambda connection: (line_order[connection.line.name], connection.stop))
    stops = {stop.stop: stop for stop in stations.values() if stop.stop in connections}
    return TransitMap(city, dict(sorted(stops.items())), lines, connections)


def straight_line_km(a: JourneyState, b: JourneyState) -> float:
    """
    Returns the great-circle distance between two stops in kilometers.
    """
    lat1, lon1, lat2, lon2 = map(radians, (a.lat, a.lon, b.lat, b.lon))
    h = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * asin(sqrt(h))


class Projection:
    """
    Maps stop coordinates to image coordinates, fitting the given stops into
    the given width. Uses an equirectangular projection, which is accurate
    enough at the scale of a city.
    """
    def __init__(self, stops: Iterable[JourneyState], width: float, margin: float = 20):
        stops = list(stops)
        self.factor = cos(radians(sum(stop.lat for stop in stops) / len(stops)))
        xs = [stop.lon * self.factor for stop in stops]
        ys = [-stop.lat for stop in stops]
        self.left, self.top, self.margin = min(xs), min(ys), margin
        self.scale = (width - 2 * margin) / max(max(xs) - self.left, 1e-3)
        self.width = width
        self.height = (max(ys) - self.top) * self.scale + 2 * margin

    def __call__(self, stop: JourneyState) -> tuple[float, float]:
        return (self.margin + (stop.lon * self.factor - self.left) * self.scale,
                self.margin + (-stop.lat - self.top) * self.scale)


def label_svg(x: float, y: float, text: str, size: float = 9) -> str:
    """
    Returns an SVG text label next to the given point, with a white outline.
    """
    return (f'<text x="{x + 5:.1f}" y="{y + 3:.1f}" font-size="{size}" stroke="white" '
            f'stroke-width="2.5" paint-order="stroke">{escape(text)}</text>')


def label_width(project: Projection, stops: Iterable[JourneyState], size: float = 9) -> float:
    """
    Returns the image width needed to fit labels next to the given stops,
    estimating the text widths.
    """
    return max(project(stop)[0] + 5 + 0.6 * size * len(stop.stop) for stop in stops)


def network_svg(transit_map: TransitMap, project: Projection, faded: bool = False) -> list[str]:
    """
    Returns SVG elements depicting all lines and stops of a transit map, in
    their line colors, or in light gray if `faded` is True.
    """
    # collect the segments of each line, ignoring direction
    segments = {}
    lines_at = {name: [] for name in transit_map.stops}
    for origin, options in transit_map.connections.items():
        for connection in options:
            segments.setdefault(connection.line, set()).add(tuple(sorted((origin, connection.stop))))
            if connection.line not in lines_at[origin]:
                lines_at[origin].append(connection.line)

    # draw lines, with buses at the bottom and metro lines on top
    stroke_width = {'metro': 4, 'tram': 2.5, 'rail': 2.5, 'bus': 1.5}
    parts = []
    for line in sorted(segments, key=lambda line: -MODES.index(line.mode)):
        color = '#d8d8d8' if faded else line.color
        width = stroke_width[line.mode] * (0.75 if faded else 1)
        parts.append(f'<g stroke="{color}" stroke-width="{width:g}" stroke-linecap="round">'
                     f'<title>{escape(line.name)}</title>')
        for a, b in sorted(segments[line]):
            (x1, y1), (x2, y2) = project(transit_map.stops[a]), project(transit_map.stops[b])
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
        parts.append('</g>')

    # draw stops
    radius = 1.5 if faded else 2
    stroke = '#bbb' if faded else 'black'
    for name, stop in transit_map.stops.items():
        x, y = project(stop)
        served = ', '.join(line.name for line in lines_at[name])
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius}" fill="white" stroke="{stroke}" '
                     f'stroke-width="1"><title>{escape(name)}\n{escape(served)}</title></circle>')
    return parts


def map_svg(transit_map: TransitMap, width: float = 900, labels: bool | None = None) -> str:
    """
    Returns an SVG image of a transit map. Stops are labeled with their names
    if `labels` is True, or if it is None and the map has at most 200 stops.
    Hover over stops and lines for details.
    """
    if labels is None:
        labels = len(transit_map.stops) <= 200
    project = Projection(transit_map.stops.values(), width)
    parts = network_svg(transit_map, project)
    if labels:
        stops = transit_map.stops.values()
        parts.extend(label_svg(*project(stop), stop.stop) for stop in stops)
        width = max(width, label_width(project, stops))
    return svg_document(''.join(parts), width, project.height)


def draw_map(transit_map: TransitMap, width: float = 900, labels: bool | None = None):
    """
    Displays a transit map. Stops are labeled with their names if `labels` is
    True, or if it is None and the map has at most 200 stops. Hover over stops
    and lines for details.
    """
    show_svg(map_svg(transit_map, width, labels))


def journey_steps(node) -> list:
    """
    Returns the sequence of search nodes leading to the given node.
    """
    if node is None:
        raise ValueError("there is no journey to show (the search found no solution)")
    steps = [node]
    while steps[0].parent is not None:
        steps.insert(0, steps[0].parent)
    return steps


def segment_svg(project: Projection, a: JourneyState, b: JourneyState, line: Line, tooltip: str) -> str:
    """
    Returns an SVG line for a ride between two stops, in the line's color.
    """
    (x1, y1), (x2, y2) = project(a), project(b)
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{line.color}" '
            f'stroke-width="5" stroke-linecap="round"><title>{escape(tooltip)}</title></line>')


def marker_svg(project: Projection, stop: JourneyState, kind: str, tooltip: str) -> str:
    """
    Returns an SVG marker for a stop: a filled circle for kind 'start', a ring
    for 'goal', and a small circle otherwise.
    """
    x, y = project(stop)
    if kind == 'start':
        marker = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="black"/>'
    elif kind == 'goal':
        marker = (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="white" stroke="black" stroke-width="2"/>'
                  f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="black"/>')
    else:
        marker = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.5" fill="white" stroke="black" stroke-width="1.5"/>'
    return f'<g><title>{escape(tooltip)}</title>{marker}</g>'


def labels_svg(project: Projection, stops: Iterable[JourneyState], width: float) -> tuple[list[str], float]:
    """
    Returns SVG labels for the given stops (each name only once), and the
    image width needed to fit them.
    """
    stops = list({stop.stop: stop for stop in stops}.values())
    return ([label_svg(*project(stop), stop.stop, size=10) for stop in stops],
            max(width, label_width(project, stops, size=10)))


def journey_svg(node, transit_map: TransitMap | None = None, width: float = 900) -> str:
    """
    Returns an SVG image of the journey leading to the given search node.
    If a transit map is given, the journey is drawn on top of it (faded),
    otherwise only the journey is drawn.
    """
    steps = journey_steps(node)
    stops = [step.state for step in steps]
    project = Projection(transit_map.stops.values() if transit_map else stops, width)
    parts = network_svg(transit_map, project, faded=True) if transit_map else []

    # draw the route in the line colors
    for i, step in enumerate(steps[1:], 1):
        parts.append(segment_svg(project, stops[i - 1], stops[i], step.action.line, f"{i}. {step.action}"))

    # draw and label the stops along the route, marking start and goal
    for i, stop in enumerate(stops):
        kind = 'start' if i == 0 else 'goal' if i == len(stops) - 1 else 'stop'
        parts.append(marker_svg(project, stop, kind, f"{stop.stop} (stop {i} of {len(stops) - 1})"))
    labels, width = labels_svg(project, stops, width)
    return svg_document(''.join(parts + labels), width, project.height)


def draw_journey(node, transit_map: TransitMap | None = None, width: float = 900):
    """
    Displays the journey leading to the given search node, with the start
    marked by a filled circle and the goal by a ring. If a transit map is
    given, the journey is drawn on top of it (faded). Hover over the route for
    the actions taken.
    """
    show_svg(journey_svg(node, transit_map, width))


def journey_expansions_svg(expansions, transit_map: TransitMap, solution=None,
                           width: float = 900) -> str:
    """
    Returns an SVG image of all nodes expanded by a search algorithm, drawn on
    top of the transit map (faded). See `draw_journey_expansions()`.
    """
    expanded = [node for node, _ in expansions]
    if not expanded:
        raise ValueError("no expansions to draw")
    project = Projection(transit_map.stops.values(), width)
    parts = network_svg(transit_map, project, faded=True)

    # draw the ride leading to each expanded node, in order of expansion
    numbers = {}  # stop name -> expansion numbers
    for i, node in enumerate(expanded, 1):
        numbers.setdefault(node.state.stop, []).append(i)
        if node.parent is not None:
            parts.append(segment_svg(project, node.parent.state, node.state, node.action.line,
                                     f"#{i}: {node.action}"))
    if solution is not None and solution.parent is not None and solution not in expanded:
        parts.append(segment_svg(project, solution.parent.state, solution.state, solution.action.line,
                                 f"goal: {solution.action}"))

    # draw and label the stops, marking start and goal
    stops = {node.state.stop: node.state for node in expanded}
    if solution is not None:
        stops.setdefault(solution.state.stop, solution.state)
    starts = {node.state.stop for node in expanded if node.parent is None}
    goal = solution.state.stop if solution is not None else None
    for name, stop in stops.items():
        kind = 'goal' if name == goal else 'start' if name in starts else 'stop'
        tooltip = ', '.join(f"#{i}" for i in numbers.get(name, [])) or "not expanded"
        parts.append(marker_svg(project, stop, kind, f"{name}: {tooltip}"))
    labels, width = labels_svg(project, stops.values(), width)
    return svg_document(''.join(parts + labels), width, project.height)


def draw_journey_expansions(expansions, transit_map: TransitMap, solution=None, width: float = 900):
    """
    Displays all nodes expanded by a search algorithm on the transit map, each
    with the ride leading to it in the line's color. `expansions` lists the
    expanded nodes in order, each with its successor nodes, as pairs
    `(node, children)`. The start is marked by a filled circle; if `solution`
    is a node, its stop is marked by a ring. Hover over stops for the order of
    expansion (#1, #2, ...).
    """
    show_svg(journey_expansions_svg(expansions, transit_map, solution, width))


def print_journey(node):
    """
    Prints the journey leading to the given search node as a list of legs,
    merging consecutive stops on the same line.
    """
    steps = journey_steps(node)
    start, goal = steps[0].state.stop, steps[-1].state.stop
    if len(steps) == 1:
        print(f"Already at {start}, no need to travel.")
        return
    legs = []  # pairs of line and list of stops, including the stop the leg starts from
    for previous, step in zip(steps, steps[1:]):
        if not legs or legs[-1][0] != step.action.line:
            legs.append((step.action.line, [previous.state.stop]))
        legs[-1][1].append(step.state.stop)
    changes = len(legs) - 1
    print(f"{start} → {goal}: {len(steps) - 1} stops, "
          f"{changes} change{'s' if changes != 1 else ''}")
    name_width = max(len(line.name) for line, _ in legs)
    for line, stops in legs:
        count = len(stops) - 1
        print(f"  {line.name:<{name_width}}  {stops[0]} → {stops[-1]} "
              f"({count} stop{'s' if count != 1 else ''})")


def stop_svg(state: JourneyState, action: JourneyAction | None = None,
             font_size: float = 11) -> tuple[str, float, float]:
    """
    Returns SVG elements depicting a stop as a box with its name, framed in
    the color of the line taken to get there, along with their width and height.
    """
    width = 0.6 * font_size * len(state.stop) + 10
    height = font_size + 10
    color = action.line.color if action is not None else 'black'
    return (f'<rect x="1" y="1" width="{width - 2:g}" height="{height - 2:g}" rx="4" fill="white" '
            f'stroke="{color}" stroke-width="2"/>'
            f'<text x="{width / 2:g}" y="{height / 2:g}" text-anchor="middle" '
            f'dominant-baseline="central" font-size="{font_size:g}">{escape(state.stop)}</text>',
            width, height)


def draw_journey_tree(expansions, solution=None, max_nodes: int = 1000, fade: bool = True):
    """
    Displays the search tree(s) explored by a search algorithm on a transit
    map. `expansions` lists the expanded nodes in order, each with its
    successor nodes, as pairs `(node, children)`. Each node shows its stop,
    framed in the color of the line taken to get there; edges are labeled with
    the line. If `solution` is a node, the path leading to it is highlighted.
    Unless `fade` is False, nodes that were generated but never expanded are
    drawn faded. Hover over a node for details.
    """
    draw_search_tree(expansions, stop_svg, edge_label=lambda action: action.line.name,
                     solution=solution, max_nodes=max_nodes, fade=fade)
