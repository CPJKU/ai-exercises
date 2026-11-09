"""
Optional add-on for journey.py: zoomable and pannable versions of the map drawings.

Nothing in journey.py or drawing.py is changed. This module only builds on
their SVG functions (`map_svg()`, `journey_svg()`, `journey_expansions_svg()`)
and displays the result in a pane that can be zoomed with the mouse wheel and
panned by dragging. Labels and markers keep their size on screen while zooming.

    from zoom import draw_journey_expansions_zoom, draw_journey_zoom, draw_map_zoom

These take the same arguments as `draw_journey_expansions()`, `draw_journey()`
and `draw_map()` from journey.py, plus an optional pane `height` in pixels.
The journey and expansion drawings start zoomed in on the stops involved.
"""
from typing import Iterable
from uuid import uuid4

from IPython.display import HTML, display

import json

from journey import (JourneyState, Projection, TransitMap, journey_expansions_svg, journey_steps,
                     journey_svg, map_svg, marker_svg, segment_svg)


def view_box(project: Projection, stops: Iterable[JourneyState], pad: float = 40,
             min_size: float = 120) -> tuple[float, float, float, float]:
    """
    Returns the (x, y, width, height) of the part of a drawing that contains the
    given stops with some padding.
    """
    points = [project(stop) for stop in stops]
    xs, ys = [x for x, _ in points], [y for _, y in points]
    width = max(max(xs) - min(xs) + 2 * pad, min_size)
    height = max(max(ys) - min(ys) + 2 * pad, min_size)
    return ((min(xs) + max(xs)) / 2 - width / 2, (min(ys) + max(ys)) / 2 - height / 2, width, height)


HIGHLIGHT_JS = """
  var hl = __HL__;
  var dimmed = [], overlay = svg.querySelector(".route-overlay"), hlOn = true;
  if (hl) {
    var titles = new Set(hl.titles), names = new Set(hl.stops);
    var outside = function(el) { return !el.closest(".route-overlay"); };
    svg.querySelectorAll("line").forEach(function(l) {  // rides expanded by the search
      var t = l.querySelector("title");
      if (t && outside(l) && /^(#\\d+|goal):/.test(t.textContent) && !titles.has(t.textContent)) dimmed.push(l);
    });
    svg.querySelectorAll("g").forEach(function(g) {     // markers of expanded stops
      var t = g.firstElementChild;
      if (t && t.tagName == "title" && outside(g) && /: (#\\d|not expanded)/.test(t.textContent) &&
          !names.has(t.textContent.split(": ")[0])) dimmed.push(g);
    });
    svg.querySelectorAll("text").forEach(function(t) {  // labels
      if (outside(t) && !names.has(t.textContent)) dimmed.push(t);
    });
    var setHighlight = function(on) {
      hlOn = on;
      dimmed.forEach(function(el) { el.style.opacity = on ? hl.opacity : ""; });
      if (overlay) overlay.style.display = on ? "" : "none";
      document.getElementById("__UID__-hl").textContent = "route highlight: " + (on ? "on" : "off");
    };
    document.getElementById("__UID__-hl-wrap").style.display = "";
    document.getElementById("__UID__-hl").onclick = function(e) { e.preventDefault(); setHighlight(!hlOn); };
    setHighlight(true);
  }
"""


def show_zoomable(svg: str, view: tuple[float, float, float, float] | None = None, height: int = 600,
                  highlight: dict | None = None):
    """
    Displays an SVG image in a pane of the given height (in pixels), zoomable
    with the mouse wheel and pannable by dragging. The pane starts at `view`
    (x, y, width, height in image coordinates) if given, otherwise showing the
    whole image. Labels and markers are drawn at a constant size on screen.
    If `highlight` is given (see `route_highlight()`), everything the search
    expanded that is not on the route is dimmed, and a link toggles this.
    """
    uid = f'zoom{uuid4().hex}'
    highlight_js = (HIGHLIGHT_JS.replace('__HL__', json.dumps(highlight)).replace('__UID__', uid)
                    if highlight else '')
    view_attr = ' '.join(f'{v:g}' for v in view) if view else ''
    display(HTML(f"""
<div id="{uid}" style="position:relative; width:100%; height:{height}px; border:1px solid #ccc;
     overflow:hidden; cursor:grab; background:white; user-select:none">
  {svg}
  <div style="position:absolute; top:6px; left:6px; font:12px sans-serif; background:rgba(255,255,255,.9);
       padding:3px 8px; border-radius:4px; border:1px solid #ddd">
    scroll = zoom &middot; drag = pan &middot;
    <a href="#" id="{uid}-fit">zoom to route</a> &middot; <a href="#" id="{uid}-all">whole map</a>
    <span id="{uid}-hl-wrap" style="display:none"> &middot; <a href="#" id="{uid}-hl">route highlight: on</a></span>
  </div>
</div>
<script>
(function() {{
  var box = document.getElementById("{uid}"), svg = box.querySelector("svg");
  svg.style.width = "100%"; svg.style.height = "100%";
  var style = document.createElementNS("http://www.w3.org/2000/svg", "style");
  style.textContent = "line, circle, text {{ vector-effect: non-scaling-stroke; }}";
  svg.insertBefore(style, svg.firstChild);
  var full = svg.getAttribute("viewBox").split(/\\s+/).map(Number);
  var init = "{view_attr}".split(/\\s+/).map(Number);
  if (init.length != 4 || init.some(isNaN)) init = full.slice();
  var v = init.slice(), drag = null, pending = false;
  function scale() {{
    var r = svg.getBoundingClientRect();
    return {{r: r, s: Math.min(r.width / v[2], r.height / v[3])}};
  }}
  function toSvg(e) {{
    var k = scale(), ox = (k.r.width - v[2] * k.s) / 2, oy = (k.r.height - v[3] * k.s) / 2;
    return {{x: v[0] + (e.clientX - k.r.left - ox) / k.s, y: v[1] + (e.clientY - k.r.top - oy) / k.s}};
  }}
  // keep labels and markers at a constant size on screen: scale them around their stop
  var items = [];
  svg.querySelectorAll("circle").forEach(function(c) {{
    items.push([c, +c.getAttribute("cx"), +c.getAttribute("cy")]);
  }});
  svg.querySelectorAll("text").forEach(function(t) {{
    items.push([t, +t.getAttribute("x") - 5, +t.getAttribute("y") - 3]);
  }});
  function resize() {{
    pending = false;
    var k = Math.min(1, 1 / scale().s);
    items.forEach(function(it) {{
      if (k == 1) it[0].removeAttribute("transform");
      else it[0].setAttribute("transform", "translate(" + it[1] + " " + it[2] + ") scale(" + k +
                              ") translate(" + (-it[1]) + " " + (-it[2]) + ")");
    }});
  }}
  function apply() {{
    svg.setAttribute("viewBox", v.join(" "));
    if (!pending) {{ pending = true; requestAnimationFrame(resize); }}
  }}
  apply();
  {highlight_js}
  svg.addEventListener("wheel", function(e) {{
    e.preventDefault();
    var p = toSvg(e), f = Math.exp(e.deltaY * 0.0015);
    v = [p.x - (p.x - v[0]) * f, p.y - (p.y - v[1]) * f, v[2] * f, v[3] * f];
    apply();
  }}, {{passive: false}});
  svg.addEventListener("mousedown", function(e) {{
    drag = {{x: e.clientX, y: e.clientY}}; box.style.cursor = "grabbing"; e.preventDefault();
  }});
  window.addEventListener("mouseup", function() {{ drag = null; box.style.cursor = "grab"; }});
  window.addEventListener("mousemove", function(e) {{
    if (!drag || !document.body.contains(box)) return;
    var s = scale().s;
    v[0] -= (e.clientX - drag.x) / s; v[1] -= (e.clientY - drag.y) / s;
    drag = {{x: e.clientX, y: e.clientY}}; apply();
  }});
  svg.addEventListener("dblclick", function() {{ v = init.slice(); apply(); }});
  document.getElementById("{uid}-fit").onclick = function(e) {{ e.preventDefault(); v = init.slice(); apply(); }};
  document.getElementById("{uid}-all").onclick = function(e) {{ e.preventDefault(); v = full.slice(); apply(); }};
}})();
</script>"""))


def draw_map_zoom(transit_map: TransitMap, width: float = 900, labels: bool | None = None,
                  height: int = 600):
    """
    Zoomable version of `draw_map()`.
    """
    show_zoomable(map_svg(transit_map, width, labels), height=height)


def draw_journey_zoom(node, transit_map: TransitMap | None = None, width: float = 900,
                      height: int = 600):
    """
    Zoomable version of `draw_journey()`, starting zoomed in on the journey.
    """
    stops = [step.state for step in journey_steps(node)]
    project = Projection(transit_map.stops.values() if transit_map else stops, width)
    show_zoomable(journey_svg(node, transit_map, width), view_box(project, stops), height)


def route_highlight(expansions, transit_map: TransitMap, solution, width: float = 900,
                    dim: float = 0.6) -> tuple[str, dict]:
    """
    Prepares highlighting the route to `solution` in an expansions drawing.
    Returns SVG elements that draw the route on top (with a dark casing and
    the stops along it), and the data `show_zoomable()` needs to dim
    everything else by the fraction `dim`.
    """
    steps = journey_steps(solution)
    project = Projection(transit_map.stops.values(), width)
    on_route = set(steps)
    expanded = [node for node, _ in expansions]
    # the tooltips that journey_expansions_svg() gives the rides on the route
    titles = [f"#{i}: {node.action}" for i, node in enumerate(expanded, 1)
              if node in on_route and node.parent is not None]
    if solution.parent is not None and solution not in expanded:
        titles.append(f"goal: {solution.action}")

    parts = []
    for i, (previous, step) in enumerate(zip(steps, steps[1:]), 1):
        (x1, y1), (x2, y2) = project(previous.state), project(step.state)
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="black" '
                     f'stroke-width="9" stroke-linecap="round" opacity="0.85"/>')
        parts.append(segment_svg(project, previous.state, step.state, step.action.line, f"{i}. {step.action}"))
    for i, step in enumerate(steps):
        kind = 'start' if i == 0 else 'goal' if i == len(steps) - 1 else 'stop'
        parts.append(marker_svg(project, step.state, kind, f"{step.state.stop} (stop {i} of {len(steps) - 1})"))
    overlay = '<g class="route-overlay">' + ''.join(parts) + '</g>'
    return overlay, {'titles': titles, 'stops': [step.state.stop for step in steps], 'opacity': 1 - dim}


def draw_journey_expansions_zoom(expansions, transit_map: TransitMap, solution=None,
                                 width: float = 900, height: int = 600, highlight: bool = True,
                                 dim: float = 0.6):
    """
    Zoomable version of `draw_journey_expansions()`, starting zoomed in on all
    stops that were expanded (and the solution). If `solution` is given and
    `highlight` is True, the route to it is drawn on top and everything else
    the search expanded is dimmed by the fraction `dim` (a link toggles this).
    """
    stops = {node.state.stop: node.state for node, _ in expansions}
    if solution is not None:
        stops.setdefault(solution.state.stop, solution.state)
    project = Projection(transit_map.stops.values(), width)
    svg = journey_expansions_svg(expansions, transit_map, solution, width)
    info = None
    if solution is not None and highlight:
        overlay, info = route_highlight(expansions, transit_map, solution, width, dim)
        svg = svg[:svg.rindex('</svg>')] + overlay + '</svg>'
    show_zoomable(svg, view_box(project, stops.values()), height, info)
