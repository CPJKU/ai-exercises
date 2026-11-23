"""
Helpers for drawing the elevator and its Q-values as SVG in Jupyter notebooks.
"""
import json
from html import escape
from uuid import uuid4

from IPython.display import HTML, display

from .elevator import (ACTIONS, ACTION_NAMES, GOING_UP, N_FLOORS, STOP,
                      unfinished)

UP_COLOR, DOWN_COLOR, CAR_COLOR = '#2e9b57', '#e08a1e', '#1976d2'
SLAB, WALL, SHAFT_BG = '#cfd8dc', '#b0bec5', '#eceff1'
IDLE, TEXT, MUTED = '#cfd8dc', '#37474f', '#90a4ae'

BUILDING_W, PANEL_W, HEIGHT = 340, 290, 450
FLOOR_GAP = 80
def _row(floor: int) -> int:
    """
    Returns the y coordinate of a floor, with floor 0 at the bottom.
    """
    return 370 - floor * FLOOR_GAP


def _person(x: float, y: float, going_up: bool) -> str:
    """
    Returns a little figure waiting on a landing: head, body and two legs,
    coloured by the direction it wants to travel.
    """
    color = UP_COLOR if going_up else DOWN_COLOR
    return (f'<circle cx="{x}" cy="{y - 11}" r="6" fill="{color}"/>'
            f'<rect x="{x - 5.5}" y="{y - 4}" width="11" height="17" rx="3.5" '
            f'fill="{color}"/>'
            f'<line x1="{x - 3}" y1="{y + 13}" x2="{x - 3}" y2="{y + 20}" '
            f'stroke="{color}" stroke-width="2.4"/>'
            f'<line x1="{x + 3}" y1="{y + 13}" x2="{x + 3}" y2="{y + 20}" '
            f'stroke="{color}" stroke-width="2.4"/>')


def _call_plate(floor: int, y: float, up_lit: bool, down_lit: bool) -> str:
    """
    Returns the little button plate on the wall, showing only the buttons that
    exist on this floor.
    """
    parts = [f'<rect x="156" y="{y - 20}" width="20" height="40" rx="3" '
             f'fill="#f5f7f8" stroke="{WALL}"/>']
    if floor < N_FLOORS - 1:
        parts.append(f'<polygon points="161,{y - 4} 166,{y - 13} 171,{y - 4}" '
                     f'fill="{UP_COLOR if up_lit else IDLE}"/>')
    if floor > 0:
        parts.append(f'<polygon points="161,{y + 6} 166,{y + 15} 171,{y + 6}" '
                     f'fill="{DOWN_COLOR if down_lit else IDLE}"/>')
    return ''.join(parts)


def _building(state, last_action=None) -> str:
    """
    Returns the building in cross-section: floor slabs, call plates, waiting
    people, the shaft with its landing doors, and the cabin on its rope.
    """
    floor, direction, up, down, car = state
    cy, doors_open = _row(floor), last_action == STOP
    parts = [f'<rect x="32" y="14" width="286" height="392" rx="6" '
             f'fill="#f7f9fa" stroke="{WALL}" stroke-width="1.4"/>',
             f'<rect x="186" y="20" width="128" height="380" '
             f'fill="{SHAFT_BG}" stroke="{WALL}"/>']
    for rail in (193, 307):                       # the car's guide rails
        parts.append(f'<line x1="{rail}" y1="22" x2="{rail}" y2="398" '
                     f'stroke="#b6c2cb" stroke-width="1.6"/>')

    for f in range(N_FLOORS):
        y = _row(f)
        parts.append(f'<rect x="34" y="{y + 28}" width="282" height="6" fill="{SLAB}"/>')
        parts.append(f'<text x="14" y="{y + 4}" font-size="13" font-weight="bold" '
                     f'fill="{TEXT}">F{f}</text>')
        if f != floor:                            # landing doors, shut
            parts.append(f'<rect x="199" y="{y - 10}" width="102" height="34" '
                         f'fill="#dde3e8" stroke="#c3ccd3"/>')
            parts.append(f'<line x1="250" y1="{y - 10}" x2="250" y2="{y + 24}" '
                         f'stroke="#c3ccd3" stroke-width="1.2"/>')
        parts.append(_call_plate(f, y, bool(up[f]), bool(down[f])))
        # one figure per lit lamp: a lamp stands for however many people
        for i, going_up in enumerate([True] * up[f] + [False] * down[f]):
            parts.append(_person(56 + i * 26, y, going_up))

    parts.append(f'<line x1="250" y1="22" x2="250" y2="{cy - 30}" '
                 f'stroke="#78909c" stroke-width="1.4"/>')          # hoist rope
    parts.append(f'<rect x="200" y="{cy + 28}" width="100" height="4" fill="{SLAB}"/>')
    parts.append(f'<rect x="196" y="{cy - 28}" width="108" height="56" rx="4" '
                 f'fill="#ffffff" stroke="{CAR_COLOR}" stroke-width="2"/>')

    if doors_open:                                # leaves slid into the walls
        for dx in (199, 287):
            parts.append(f'<rect x="{dx}" y="{cy - 10}" width="14" height="34" '
                         f'fill="#90caf9" stroke="{CAR_COLOR}" stroke-width="0.8"/>')
    else:                                         # shut: they really do hide the inside
        for dx in (199, 250):
            parts.append(f'<rect x="{dx}" y="{cy - 10}" width="51" height="34" '
                         f'fill="#cfd9e2" stroke="#90a4ae" stroke-width="0.9"/>')
        parts.append(f'<line x1="250" y1="{cy - 10}" x2="250" y2="{cy + 24}" '
                     f'stroke="#78909c" stroke-width="1.6"/>')

    # the indicator panel, inside the cabin above the doors like a real lift:
    # which way we are committed, and which buttons the passengers have pressed.
    # The floor number is not repeated here — the drawing already shows it.
    parts.append(f'<rect x="199" y="{cy - 26}" width="102" height="15" rx="2" '
                 f'fill="#263238"/>')
    arrow = ('#80deea' if last_action != STOP else '#78909c')   # grey while stopped
    points = (f'211,{cy - 24} 217,{cy - 15} 205,{cy - 15}' if direction == GOING_UP
              else f'211,{cy - 15} 217,{cy - 24} 205,{cy - 24}')
    parts.append(f'<polygon points="{points}" fill="{arrow}"/>')
    for f in range(N_FLOORS):
        bx, lit = 229 + f * 15, car[f]
        parts.append(f'<circle cx="{bx}" cy="{cy - 18.5}" r="6.5" '
                     f'fill="{"#80deea" if lit else "#37474f"}"/>')
        parts.append(f'<text x="{bx}" y="{cy - 18.5}" font-size="7" font-weight="bold" '
                     f'text-anchor="middle" dominant-baseline="central" '
                     f'fill="{"#102027" if lit else "#8aa0ab"}">{f}</text>')
    return ''.join(parts)


def _q_values(q_values) -> str:
    """
    Returns a bar chart of the Q-values of the current state. Every value is
    negative, so the shortest bar is the best action.
    """
    best = max(ACTIONS, key=lambda a: q_values[a])
    worst = max(max(abs(v) for v in q_values), 1e-9)
    parts = [f'<text x="352" y="44" font-size="13" font-weight="bold" '
             f'fill="{TEXT}">Q-values of current state</text>']
    for action in ACTIONS:
        y = 78 + action * 34
        color = CAR_COLOR if action == best else '#c7d0d6'
        width = max(3, 150 * abs(q_values[action]) / worst)
        parts.append(f'<text x="352" y="{y + 15}" font-size="12" '
                     f'fill="{TEXT}">{ACTION_NAMES[action]}</text>')
        parts.append(f'<rect x="400" y="{y}" width="{width:g}" height="20" rx="3" '
                     f'fill="{color}"/>')
        parts.append(f'<text x="{400 + width + 6:g}" y="{y + 15}" font-size="11" '
                     f'font-weight="{"bold" if action == best else "normal"}" '
                     f'fill="{color if action == best else "#546e7a"}">'
                     f'{q_values[action]:.1f}</text>')
    parts.append(f'<text x="352" y="196" font-size="12" fill="{MUTED}">'
                 f'shorter bar = higher Q = better</text>')
    return ''.join(parts)


def frame_svg(state, q_values=None, last_action=None, caption='') -> str:
    """
    Returns one frame as a complete SVG image. Without `q_values` only the
    building is drawn, in a correspondingly narrower image.
    """
    width = BUILDING_W + PANEL_W if q_values is not None else BUILDING_W
    body = _building(state, last_action)
    if q_values is not None:
        body += _q_values(q_values)
    if caption:
        body += (f'<text x="14" y="{HEIGHT - 14}" font-size="11" '
                 f'fill="{TEXT}">{escape(caption)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{HEIGHT}" viewBox="0 0 {width} {HEIGHT}" '
            f'font-family="sans-serif">'
            f'<rect width="{width}" height="{HEIGHT}" fill="white"/>{body}</svg>')


def draw_state(state, q_values=None, last_action=None, caption=''):
    """
    Draws one elevator state, optionally with the Q-values of that state.
    """
    display(HTML(frame_svg(state, q_values, last_action, caption)))


def draw_episode(states, actions, q_table=None, interval: int = 500):
    """
    Draws a whole episode as an animation you can play, step and scrub through.
    """
    frames = []
    for i, state in enumerate(states):
        last = actions[i - 1] if i else None
        values = None if q_table is None else list(q_table[state])
        caption = (f'tick {i}   ·   lamps still lit {unfinished(state)}'
                   f'   ·   last action {ACTION_NAMES.get(last, "-")}')
        frames.append(frame_svg(state, values, last, caption))

    # A unique id per drawing: several episodes can live in one notebook, and a
    # script inserted via innerHTML cannot find itself with document.currentScript.
    box = 'episode_' + uuid4().hex[:8]
    payload = json.dumps(frames)
    display(HTML(f"""
<div id="{box}">
  <div class="frame">{frames[0]}</div>
  <div style="margin-top:6px; font:13px sans-serif">
    <button class="play">&#9654; Play</button>
    <button class="step">Step</button>
    <input class="slider" type="range" min="0" max="{len(frames) - 1}" value="0"
           style="vertical-align:middle; width:240px">
    <span class="label" style="color:#546e7a">1 / {len(frames)}</span>
  </div>
</div>
<script>
(function() {{
  var root = document.getElementById("{box}");
  if (!root) return;                       // nothing to hook up
  var frames = {payload};
  var box = root.querySelector(".frame"), slider = root.querySelector(".slider");
  var label = root.querySelector(".label"), play = root.querySelector(".play");
  var timer = null;
  function show(i) {{
    box.innerHTML = frames[i];
    slider.value = i;
    label.textContent = (i + 1) + " / " + frames.length;
  }}
  function stop() {{
    if (timer) clearInterval(timer);
    timer = null;
    play.innerHTML = "&#9654; Play";
  }}
  slider.addEventListener("input", function(e) {{ stop(); show(+e.target.value); }});
  root.querySelector(".step").addEventListener("click", function() {{
    stop(); show((+slider.value + 1) % frames.length);
  }});
  play.addEventListener("click", function() {{
    if (timer) return stop();
    if (+slider.value >= frames.length - 1) show(0);
    play.innerHTML = "&#10073;&#10073; Pause";
    timer = setInterval(function() {{
      var next = +slider.value + 1;
      if (next >= frames.length) return stop();
      show(next);
    }}, {interval});
  }});
}})();
</script>"""))


def plot_learning_curve(history, window: int = 5000):
    """
    Plots the reward per episode during training, averaged over `window` episodes.
    """
    import matplotlib.pyplot as plt

    xs = list(range(0, len(history) - window, 1000))
    averages = [sum(history[x:x + window]) / window for x in xs]
    plt.figure(figsize=(7, 3))
    plt.plot(xs, averages)
    plt.xlabel("episode")
    plt.ylabel("reward per episode")
    plt.title("Learning curve")
    plt.tight_layout()
    plt.show()
