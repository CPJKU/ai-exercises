"""
Draws how minimax and alpha-beta search build their game tree, as an animation.

The tree is drawn once. Then the search is replayed as a short list of events
(visit a state, update its value, prune its remaining moves, ...) that the
browser applies one after the other.
"""
import json
import math
import sys
from html import escape
from uuid import uuid4

from IPython.display import HTML, display

X_COLOR, O_COLOR, DONE_COLOR = '#1976d2', '#e08a1e', '#90a4ae'     # MAX, MIN, game over
X_TINT, O_TINT, DRAW_TINT = '#e3f2fd', '#fff3e0', '#eceff1'
TEXT, MUTED = '#37474f', '#90a4ae'

PITCH = 44        # horizontal space per leaf
LEVEL = 96        # vertical space per level of the tree
MARGIN = 26


class _Node:
    def __init__(self, index, state, parent, move):
        self.index, self.state, self.parent, self.move = index, state, parent, move
        self.children = []
        self.depth = 0 if parent is None else None
        self.x = self.y = 0


def _build_tree(game, state) -> list[_Node]:
    """
    Returns every state below `state`, in the order a depth-first search meets them.
    """
    nodes = []

    def make(state, parent, move, depth):
        node = _Node(len(nodes), state, parent, move)
        node.depth = depth
        nodes.append(node)
        for action, next_state in game.successors(state):
            node.children.append(make(next_state, node.index, action, depth + 1).index)
        return node

    make(state, None, None, 0)
    return nodes


def _layout(nodes):
    """
    Gives every state a position: leaves side by side, parents centred above
    their children.
    """
    next_leaf = [MARGIN + PITCH / 2]

    def place(i):
        node = nodes[i]
        node.y = 20 + node.depth * LEVEL
        if not node.children:
            node.x = next_leaf[0]
            next_leaf[0] += PITCH
        else:
            xs = [place(c) for c in node.children]
            node.x = (xs[0] + xs[-1]) / 2
        return node.x

    place(0)
    return int(next_leaf[0] + MARGIN)


def _value(v) -> str:
    """
    Formats a utility, or an infinity, for display.
    """
    if v == math.inf:
        return '+∞'
    if v == -math.inf:
        return '−∞'
    return '0' if v == 0 else (f'+{v}' if v > 0 else f'−{-v}')


def _tone(v) -> str:
    """
    Tells the browser how to colour a value: x (good for MAX), o (good for MIN) or draw.
    """
    return 'd' if v == 0 or abs(v) == math.inf else ('x' if v > 0 else 'o')


def _trace(game, nodes, algorithm):
    """
    Runs the search and records what happens, as a list of events.
    """
    alphabeta = algorithm == 'alphabeta'
    who = lambda s: 'X (MAX)' if game.is_max_turn(s) else 'O (MIN)'
    events = []
    best = {}                                  # state -> the move that gave its value

    def bounds(alpha, beta):
        return f'α={_value(alpha)}  β={_value(beta)}' if alphabeta else ''

    def visit(i, alpha, beta):
        node = nodes[i]
        if not node.children:                                   # the game is over
            u = game.utility(node.state)
            outcome = {1: 'X has won', -1: 'O has won', 0: 'a draw'}[u]
            events.append({'k': 'leaf', 'n': i, 'label': _value(u), 'tone': _tone(u),
                           'caption': f'Game over: {outcome}, so its utility is {_value(u)}.'})
            return u
        maxing = game.is_max_turn(node.state)
        events.append({'k': 'enter', 'n': i, 'bounds': bounds(alpha, beta),
                       'caption': f'Look at this state. It is {who(node.state)}\'s turn, '
                                  f'and there are {len(node.children)} moves to try.'})
        v = -math.inf if maxing else math.inf
        for position, child in enumerate(node.children):
            cv = visit(child, alpha, beta)
            if (cv > v) if maxing else (cv < v):
                best[i] = child                # the first move to reach the best value
            v = max(v, cv) if maxing else min(v, cv)
            cut = alphabeta and (v >= beta if maxing else v <= alpha)
            if alphabeta and not cut:
                alpha, beta = (max(alpha, v), beta) if maxing else (alpha, min(beta, v))
            what = 'largest' if maxing else 'smallest'
            events.append({'k': 'upd', 'n': i, 'label': ('≥ ' if maxing else '≤ ') + _value(v),
                           'tone': _tone(v), 'bounds': bounds(alpha, beta),
                           'caption': f'A move returned {_value(cv)}. The {what} value so far '
                                      f'is {_value(v)}.'})
            if cut:
                rest = node.children[position + 1:]
                if rest:
                    if maxing:
                        test = f'{_value(v)} ≥ β = {_value(beta)}'
                        reason = (f'MIN higher up can already get {_value(beta)} somewhere '
                                  f'else, so it will never allow this state.')
                    else:
                        test = f'{_value(v)} ≤ α = {_value(alpha)}'
                        reason = (f'MAX higher up can already get {_value(alpha)} somewhere '
                                  f'else, so it will never choose this state.')
                    moves = 'move' if len(rest) == 1 else 'moves'
                    events.append({'k': 'prune', 'n': i, 'skipped': rest,
                                   'caption': f'Prune! {test}. {reason} The remaining '
                                              f'{len(rest)} {moves} cannot change the result.'})
                break
        events.append({'k': 'leave', 'n': i, 'label': _value(v), 'tone': _tone(v),
                       'caption': f'All moves are done. The value of this state is {_value(v)}.'})
        return v

    visit(0, -math.inf, math.inf)
    return events, best


def _board_svg(state, move, x, y) -> str:
    """
    Returns a little 3x3 board with its top left corner at (x, y). The cell that
    was just played is highlighted.
    """
    parts = [f'<rect x="{x}" y="{y}" width="30" height="30" fill="white"/>']
    if move is not None:
        parts.append(f'<rect x="{x + move % 3 * 10}" y="{y + move // 3 * 10}" width="10" '
                     f'height="10" fill="#fff0b3"/>')
    for k in (10, 20):
        parts.append(f'<line x1="{x + k}" y1="{y + 1}" x2="{x + k}" y2="{y + 29}" '
                     f'stroke="#b0bec5" stroke-width="1"/>')
        parts.append(f'<line x1="{x + 1}" y1="{y + k}" x2="{x + 29}" y2="{y + k}" '
                     f'stroke="#b0bec5" stroke-width="1"/>')
    for cell, mark in enumerate(state):
        cx, cy = x + cell % 3 * 10 + 5, y + cell // 3 * 10 + 5
        if mark == 'X':
            parts.append(f'<path d="M{cx - 3} {cy - 3}L{cx + 3} {cy + 3}M{cx + 3} {cy - 3}'
                         f'L{cx - 3} {cy + 3}" stroke="{X_COLOR}" stroke-width="1.7" fill="none"/>')
        elif mark == 'O':
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="3.2" stroke="{O_COLOR}" '
                         f'stroke-width="1.7" fill="none"/>')
    return ''.join(parts)


def _cut_mark(ident, x1, y1, x2, y2) -> str:
    """
    Returns two short red bars across the middle of an edge: the usual way to
    show that a branch was cut off.
    """
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length                    # along the edge
    nx, ny = -uy * 7, ux * 7                             # across it
    mx, my = x1 + dx * 0.55, y1 + dy * 0.55
    bars = ''.join(f'<line x1="{mx + k * ux * 3 - nx:.1f}" y1="{my + k * uy * 3 - ny:.1f}" '
                   f'x2="{mx + k * ux * 3 + nx:.1f}" y2="{my + k * uy * 3 + ny:.1f}" '
                   f'stroke="#d32f2f" stroke-width="2.2" stroke-linecap="round"/>'
                   for k in (-1, 1))
    return f'<g id="{ident}" style="opacity:0">{bars}</g>'


def _big_board(state, move, size, border=None) -> str:
    """
    Returns a board as a standalone SVG of the given size in pixels.
    """
    frame = (f'<rect x="0.75" y="0.75" width="28.5" height="28.5" fill="none" '
             f'stroke="{border}" stroke-width="1.5"/>' if border else '')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-1 -1 32 32" width="{size}" '
            f'height="{size}" style="display:block">{_board_svg(state, move, 0, 0)}{frame}</svg>')


def _trace_function(game, nodes, function):
    """
    Runs the student's own search `function` and records what it does, as a list
    of events. Every call of the function is caught while it runs, together with
    its arguments and what it returns, so nothing is assumed about how it is written.
    """
    alphabeta = 'alpha' in function.__code__.co_varnames[:function.__code__.co_argcount]
    code = function.__code__
    root, stack = [], []

    def watch(frame, event, arg):
        if frame.f_code is not code:
            return
        if event == 'call':
            record = {'state': frame.f_locals.get('state'), 'alpha': frame.f_locals.get('alpha'),
                      'beta': frame.f_locals.get('beta'), 'ret': None, 'calls': []}
            (stack[-1]['calls'] if stack else root).append(record)
            stack.append(record)
        elif event == 'return':
            stack.pop()['ret'] = arg

    run = type(game)()
    sys.setprofile(watch)
    try:
        function(run, nodes[0].state)
    finally:
        sys.setprofile(None)
    if not root or root[0]['ret'] is None:
        raise ValueError('your function returned None: implement it first')

    who = lambda s: 'X (MAX)' if game.is_max_turn(s) else 'O (MIN)'
    value_of = lambda ret: ret[0] if isinstance(ret, tuple) else ret
    events, best = [], {}

    def bounds(alpha, beta):
        return f'α={_value(alpha)}  β={_value(beta)}' if alphabeta else ''

    def replay(record, i):
        node = nodes[i]
        returned = value_of(record['ret'])
        if not node.children:                                   # the game is over
            outcome = {1: 'X has won', -1: 'O has won', 0: 'a draw'}[game.utility(node.state)]
            events.append({'k': 'leaf', 'n': i, 'label': _value(returned), 'tone': _tone(returned),
                           'caption': f'Game over: {outcome}, so its utility is {_value(returned)}.'})
            return returned
        maxing = game.is_max_turn(node.state)
        alpha, beta = record['alpha'], record['beta']
        if alpha is None:
            alpha, beta = -math.inf, math.inf
        events.append({'k': 'enter', 'n': i, 'bounds': bounds(alpha, beta),
                       'caption': f'Look at this state. It is {who(node.state)}\'s turn, '
                                  f'and there are {len(node.children)} moves to try.'})
        called = {}
        for call in record['calls']:
            match = [c for c in node.children if nodes[c].state == call['state']]
            if not match:
                raise ValueError(f'your function was called with {call["state"]!r}, '
                                 f'which is not a successor of {node.state!r}')
            called[match[0]] = call
        v = -math.inf if maxing else math.inf
        seen = [c for c in node.children if c in called]
        for child in seen:
            cv = replay(called[child], child)
            v = max(v, cv) if maxing else min(v, cv)
            cut = alphabeta and (v >= beta if maxing else v <= alpha)
            if alphabeta and not cut:
                alpha, beta = (max(alpha, v), beta) if maxing else (alpha, min(beta, v))
            what = 'largest' if maxing else 'smallest'
            events.append({'k': 'upd', 'n': i, 'label': ('≥ ' if maxing else '≤ ') + _value(v),
                           'tone': _tone(v), 'bounds': bounds(alpha, beta),
                           'caption': f'A move returned {_value(cv)}. The {what} value so far '
                                      f'is {_value(v)}.'})
            rest = [c for c in node.children[node.children.index(child) + 1:] if c not in called]
            if child == seen[-1] and rest:
                moves = 'move' if len(rest) == 1 else 'moves'
                if cut and maxing:
                    why = (f'Prune! {_value(v)} ≥ β = {_value(beta)}. MIN higher up can already '
                           f'get {_value(beta)} somewhere else, so it will never allow this state.')
                elif cut:
                    why = (f'Prune! {_value(v)} ≤ α = {_value(alpha)}. MAX higher up can already '
                           f'get {_value(alpha)} somewhere else, so it will never choose this state.')
                else:
                    why = 'Your function stops here, although no cut is justified.'
                tail = 'cannot change the result' if cut else 'are not looked at'
                events.append({'k': 'prune', 'n': i, 'skipped': rest,
                               'caption': f'{why} The remaining {len(rest)} {moves} {tail}.'})
        if isinstance(record['ret'], tuple):                    # the action it chose
            chosen = [c for c in node.children if nodes[c].move == record['ret'][1]]
            if chosen:
                best[i] = chosen[0]
        events.append({'k': 'leave', 'n': i, 'label': _value(returned), 'tone': _tone(returned),
                       'caption': f'All moves are done. The value of this state is {_value(returned)}.'})
        return returned

    replay(root[0], 0)
    return events, best, alphabeta


def _who(game, state) -> str:
    return 'X' if game.is_max_turn(state) else 'O'


def _skeleton(game, nodes, box, width, height, alphabeta) -> str:
    """
    Returns the whole tree as SVG, with an id on every part the player changes.
    """
    parts = []
    for node in nodes:
        if node.parent is not None:                       # the edge down to this state
            p = nodes[node.parent]
            parts.append(f'<line id="{box}_e{node.index}" x1="{p.x}" y1="{p.y + 62}" '
                         f'x2="{node.x}" y2="{node.y - 3}" stroke="#78909c" stroke-width="1.4" '
                         f'style="opacity:0"/>')
            parts.append(_cut_mark(f'{box}_s{node.index}', p.x, p.y + 62, node.x, node.y - 3))
    for node in nodes:
        terminal = not node.children
        if terminal:
            u = game.utility(node.state)
            color, tint = DONE_COLOR, {1: X_TINT, -1: O_TINT, 0: DRAW_TINT}[u]
        else:
            maxing = game.is_max_turn(node.state)
            color, tint = (X_COLOR if maxing else O_COLOR), 'white'
        x, y = node.x, node.y
        parts.append(f'<g id="{box}_n{node.index}" style="opacity:0">'
                     f'<rect id="{box}_a{node.index}" x="{x - 21}" y="{y - 6}" width="42" '
                     f'height="42" rx="7" fill="none" stroke="#ffb300" stroke-width="3.5" '
                     f'style="display:none"/>'
                     f'<rect id="{box}_p{node.index}" x="{x - 21}" y="{y - 6}" width="42" '
                     f'height="42" rx="7" fill="none" stroke="#2e9b57" stroke-width="3.5" '
                     f'style="display:none"/>'
                     f'<rect x="{x - 18}" y="{y - 3}" width="36" height="36" rx="5" '
                     f'fill="{tint}" stroke="{color}" stroke-width="2"/>'
                     f'{_board_svg(node.state, node.move, x - 15, y)}'
                     f'<text id="{box}_v{node.index}" x="{x}" y="{y + 46}" font-size="12" '
                     f'font-weight="bold" text-anchor="middle" fill="{MUTED}"></text>'
                     + (f'<text id="{box}_b{node.index}" x="{x}" y="{y + 58}" font-size="8" '
                        f'text-anchor="middle" fill="{MUTED}"></text>' if alphabeta else '')
                     + '</g>')
    return (f'<svg class="stage" xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" font-family="sans-serif">'
            f'<rect width="{width}" height="{height}" fill="white"/>{"".join(parts)}</svg>')


def draw_search_tree(game, state, algorithm: str = 'minimax', interval: int = 800):
    """
    Draws how `algorithm` builds its search tree below `state`, as an animation.
    `algorithm` is either one of the strings 'minimax' and 'alphabeta' (our own
    version), or your own function, e.g. `algorithm=alphabeta`: then the tree shows
    what your implementation really does. Use a position with only a few free cells: the
    whole game tree is drawn, and it grows very fast.

    At the end, the best line of play is marked in green.
    """
    if not callable(algorithm) and algorithm not in ('minimax', 'alphabeta'):
        raise ValueError("algorithm must be 'minimax', 'alphabeta' or a function")
    game = type(game)()                       # a fresh game, so no counters are disturbed
    nodes = _build_tree(game, state)
    if len(nodes) > 400:
        raise ValueError(f"the tree has {len(nodes)} states, which is too many to draw: "
                         f"use a position with fewer free cells")
    width = _layout(nodes)
    height = 20 + (max(n.depth for n in nodes) + 1) * LEVEL + 10
    if callable(algorithm):
        events, best, alphabeta = _trace_function(game, nodes, algorithm)
    else:
        events, best = _trace(game, nodes, algorithm)
        alphabeta = algorithm == 'alphabeta'

    # the best line of play: from the start, always the move that gave the value
    line = [0]
    while nodes[line[-1]].children and line[-1] in best:
        line.append(best[line[-1]])
    end = nodes[line[-1]]
    if end.children:                          # the line of the search stops before a finished game
        root_label = [e['label'] for e in events if e['n'] == 0 and e['k'] == 'leave'][-1]
        root_value = {'+1': 1, '−1': -1}.get(root_label, 0)
    else:
        root_value = int(game.utility(end.state))
    outcome = {1: 'a win for X', -1: 'a win for O', 0: 'a draw'}[root_value]
    first_player = _who(game, state)
    if len(line) > 1:
        verdict = f'{first_player} has to start with cell {nodes[line[1]].move}.'
    else:
        verdict = 'The game is already over.'
    events[-1]['caption'] += f' The best line of play is marked in green: {outcome}, {verdict}'

    entered = [e for e in events if e['k'] == 'enter']
    leaves = sum(not n.children for n in nodes)
    title = 'Alpha-beta' if alphabeta else 'Minimax'

    frame = lambda n: (DONE_COLOR if not n.children
                       else (X_COLOR if game.is_max_turn(n.state) else O_COLOR))

    box = 'tree_' + uuid4().hex[:8]
    tree = [{'p': -1 if n.parent is None else n.parent, 'c': n.children, 'x': n.x, 'y': n.y,
             'frame': frame(n)} for n in nodes]
    on_line = line

    panel_title = 'font-size: 12px; color: #546e7a; margin-bottom: 3px;'
    display(HTML(f"""
<div id="{box}" style="font-family: sans-serif; color: {TEXT}; background: #ffffff; padding: 8px;">
  <div style="font-size: 12px; margin-bottom: 6px; color: #546e7a;">
    <span style="color:{X_COLOR}">&#9632;</span> X to move (MAX) &nbsp;
    <span style="color:{O_COLOR}">&#9632;</span> O to move (MIN) &nbsp;
    <span style="color:{DONE_COLOR}">&#9632;</span> game over &nbsp;
    <span style="background:#fff0b3">&nbsp;&nbsp;</span> the move just played &nbsp;
    <span style="color:#2e9b57">&#9632;</span> best line (at the end)</div>
  <div class="scroller" style="overflow-x: auto; max-width: 100%; border: 1px solid #eceff1;">
    {_skeleton(game, nodes, box, width, height, alphabeta)}</div>
  <div class="caption" style="min-height: 2.6em; margin-top: 6px; font-size: 13px;"></div>
  <div style="margin-top: 4px; font-size: 13px;">
    <button class="play">&#9654; Play</button>
    <button class="step">Step</button>
    <input class="slider" type="range" min="0" max="{len(events) - 1}" value="0"
           style="vertical-align: middle; width: 260px">
    <span class="label" style="color: #546e7a"></span>
    <span style="margin-left: 14px; color: #546e7a">Speed</span>
    <button class="slower" title="slower">&minus;</button>
    <span class="speed" style="display: inline-block; min-width: 2.6em; text-align: center"></span>
    <button class="faster" title="faster">+</button>
  </div>
</div>
<script>
(function() {{
  var root = document.getElementById("{box}");
  if (!root) return;                       // nothing to hook up
  var tree = {json.dumps(tree)}, events = {json.dumps(events, ensure_ascii=False)};
  var line = {json.dumps(on_line)};
  var BOX = "{box}", X = "{X_COLOR}", O = "{O_COLOR}", DRAW = "{MUTED}";
  var el = function(prefix, i) {{ return document.getElementById(BOX + "_" + prefix + i); }};
  var slider = root.querySelector(".slider"), label = root.querySelector(".label");
  var caption = root.querySelector(".caption"), play = root.querySelector(".play");
  var scroller = root.querySelector(".scroller"), timer = null;
  var toneColor = {{x: X, o: O, d: DRAW}};

  function subtree(i, out) {{
    out.push(i);
    tree[i].c.forEach(function(c) {{ subtree(c, out); }});
    return out;
  }}

  function show(i, scroll) {{
    var n = tree.length, visible = [], pruned = [], text = [], tone = [], bnd = [];
    for (var k = 0; k < n; k++) {{ visible.push(false); pruned.push(false); text.push(""); bnd.push(""); tone.push("d"); }}
    for (var e = 0; e <= i; e++) {{
      var ev = events[e], node = ev.n;
      visible[node] = true;
      if (ev.k === "leaf" || ev.k === "upd" || ev.k === "leave") {{ text[node] = ev.label; tone[node] = ev.tone; }}
      if (ev.bounds !== undefined) bnd[node] = ev.bounds;
      if (ev.k === "prune") {{
        ev.skipped.forEach(function(c) {{
          subtree(c, []).forEach(function(d) {{ visible[d] = true; pruned[d] = true; }});
        }});
      }}
    }}
    var finished = (i === events.length - 1);
    var onLine = [];
    for (var k = 0; k < n; k++) onLine.push(false);
    if (finished) line.forEach(function(d) {{ onLine[d] = true; }});
    var active = events[i].n;
    for (var k = 0; k < n; k++) {{
      el("n", k).style.opacity = !visible[k] ? 0 : (pruned[k] ? 0.28 : 1);
      var edge = el("e", k), scissors = el("s", k);
      if (edge) {{
        edge.style.opacity = !visible[k] ? 0 : (pruned[k] ? 0.35 : 1);
        edge.setAttribute("stroke-dasharray", pruned[k] ? "4 3" : "");
        edge.setAttribute("stroke", onLine[k] ? "#2e9b57" : "#78909c");
        edge.setAttribute("stroke-width", onLine[k] ? 3.5 : 1.4);
      }}
      if (scissors) scissors.style.opacity = (pruned[k] && !pruned[tree[k].p]) ? 1 : 0;
      el("a", k).style.display = (k === active) ? "" : "none";
      el("p", k).style.display = onLine[k] ? "" : "none";
      var v = el("v", k); v.textContent = text[k]; v.setAttribute("fill", toneColor[tone[k]]);
      var b = el("b", k); if (b) b.textContent = bnd[k];
    }}
    caption.textContent = events[i].caption;
    slider.value = i;
    label.textContent = "step " + (i + 1) + " / " + events.length;
    if (scroll) {{
      var target = tree[active].x - scroller.clientWidth / 2;
      scroller.scrollTo({{left: Math.max(0, target), behavior: "smooth"}});
    }}
  }}

  var speeds = [0.25, 0.5, 1, 2, 4, 8], level = 2;          // 1x is {interval} ms per step
  var slower = root.querySelector(".slower"), faster = root.querySelector(".faster");
  function tick() {{
    var next = +slider.value + 1;
    if (next >= events.length) return stop();
    show(next, true);
  }}
  function startTimer() {{
    timer = setInterval(tick, {interval} / speeds[level]);
  }}
  function showSpeed() {{
    root.querySelector(".speed").textContent = speeds[level] + "\u00d7";
    slower.disabled = level === 0;
    faster.disabled = level === speeds.length - 1;
  }}
  function changeSpeed(by) {{
    level = Math.max(0, Math.min(speeds.length - 1, level + by));
    showSpeed();
    if (timer) {{ clearInterval(timer); startTimer(); }}      // a running animation continues at the new speed
  }}
  slower.addEventListener("click", function() {{ changeSpeed(-1); }});
  faster.addEventListener("click", function() {{ changeSpeed(1); }});
  function stop() {{
    if (timer) clearInterval(timer);
    timer = null;
    play.innerHTML = "&#9654; Play";
  }}
  slider.addEventListener("input", function(e) {{ stop(); show(+e.target.value, true); }});
  root.querySelector(".step").addEventListener("click", function() {{
    stop(); show((+slider.value + 1) % events.length, true);
  }});
  play.addEventListener("click", function() {{
    if (timer) return stop();
    if (+slider.value >= events.length - 1) show(0, true);
    play.innerHTML = "&#10073;&#10073; Pause";
    startTimer();
  }});
  showSpeed();
  show(0, false);
}})();
</script>"""))
    return None
