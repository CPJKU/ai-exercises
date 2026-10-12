"""
Helpers for drawing states and search trees as SVG in Jupyter notebooks.
"""
from html import escape
from typing import Any, Callable, Iterable

from IPython.display import HTML, display

MARGIN = 10      # space around the whole drawing
H_GAP = 16       # horizontal space between neighboring nodes
V_GAP = 24       # vertical space between levels of the tree
FONT_SIZE = 11   # font size for edge labels and expansion numbers
TEXT_HEIGHT = 14  # vertical space reserved for a line of text
SOLUTION_COLOR = '#2a9d4b'


def svg_document(body: str, width: float, height: float) -> str:
    """
    Wraps SVG elements into a complete SVG image with a white background.
    """
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
            f'viewBox="0 0 {width:g} {height:g}" font-family="sans-serif">'
            f'<rect width="{width:g}" height="{height:g}" fill="white"/>{body}</svg>')


def show_svg(svg: str):
    """
    Displays an SVG image in a notebook, scrolling horizontally if it is too wide.
    """
    display(HTML(f'<div style="overflow-x: auto; max-width: 100%;">{svg}</div>'))


def search_tree_svg(expansions: Iterable[tuple[Any, Iterable[Any]]],
                    draw_state: Callable[[Any, Any], tuple[str, float, float]],
                    edge_label: Callable[[Any], str] | None = str,
                    solution: Any = None,
                    max_nodes: int = 1000,
                    fade: bool = True) -> str:
    """
    Returns an SVG image of the search tree(s) explored by a search algorithm.

    `expansions` lists the expanded nodes in order, each with its successor
    nodes, as pairs `(node, children)`. Nodes need `state`, `action`, and
    `parent` attributes. Expanded nodes are numbered in order of expansion,
    nodes that were generated but never expanded are drawn faded (unless
    `fade` is False). Each
    expanded node that is not a successor of another expanded node starts a
    new tree (e.g., once per iteration of iterative deepening search).

    `draw_state(state, action)` must return SVG elements depicting the state
    (drawn at the origin) along with their width and height. `edge_label`
    turns the action leading to a node into text written above the node,
    or is None to omit these labels. If `solution` is a node, the path
    leading to it is highlighted.
    """
    # collect tree structure and expansion order
    children = {}
    number = {}
    for i, (node, successors) in enumerate(expansions, 1):
        if node not in children:
            children[node] = list(successors)
            number[node] = i
    generated = {child for successors in children.values() for child in successors}
    roots = [node for node in children if node not in generated]
    if not roots:
        raise ValueError("no expansions to draw")

    # list all nodes to draw, depth first
    nodes = []
    pending = roots[::-1]
    while pending:
        node = pending.pop()
        nodes.append(node)
        if len(nodes) > max_nodes:
            raise ValueError(f"search tree has more than {max_nodes} nodes; "
                             "try a smaller problem or increase max_nodes")
        pending.extend(children.get(node, [])[::-1])

    # render all states and labels, and compute the size of a slot for a node
    drawings = {node: draw_state(node.state, node.action) for node in nodes}
    labels = {node: edge_label(node.action) if edge_label and node.action is not None else ''
              for node in nodes}
    box_height = max(height for _, _, height in drawings.values())
    label_height = TEXT_HEIGHT if edge_label else 0
    level_height = label_height + box_height + TEXT_HEIGHT + V_GAP

    def footprint(node) -> float:
        # horizontal space taken by a node's drawing and the label above it
        return max(drawings[node][1], 0.6 * FONT_SIZE * len(labels[node]))

    # place leaves from left to right and center parents above their children;
    # if a parent would overlap its left neighbor, shift its whole subtree right
    positions = {}
    next_x = MARGIN  # left edge of the next leaf
    right_edge = {}  # right edge of the rightmost node placed so far, per depth

    def shift(node, delta: float):
        nonlocal next_x
        x, depth = positions[node]
        positions[node] = (x + delta, depth)
        right_edge[depth] = max(right_edge[depth], x + delta + footprint(node) / 2)
        next_x = max(next_x, right_edge[depth] + H_GAP)
        for child in children.get(node, []):
            shift(child, delta)

    def place(node, depth: int) -> float:
        nonlocal next_x
        half = footprint(node) / 2
        successors = children.get(node, [])
        if successors:
            xs = [place(child, depth + 1) for child in successors]
            x = (xs[0] + xs[-1]) / 2
            overlap = right_edge.get(depth, float('-inf')) + H_GAP - (x - half)
            if overlap > 0:
                for child in successors:
                    shift(child, overlap)
                x += overlap
        else:
            x = next_x + half
        positions[node] = (x, depth)
        right_edge[depth] = x + half
        next_x = max(next_x, x + half + H_GAP)
        return x

    for root in roots:
        place(root, 0)
        next_x += 3 * H_GAP  # leave extra space between trees

    def top(depth: int) -> float:
        return MARGIN + depth * level_height + label_height

    # find the path to the solution
    on_path = set()
    node = solution
    while node is not None:
        on_path.add(node)
        node = node.parent

    # draw edges, then nodes on top
    parts = []
    for parent in nodes:
        px, depth = positions[parent]
        y1 = top(depth) + drawings[parent][2] + TEXT_HEIGHT
        y2 = top(depth + 1) - label_height
        for child in children.get(parent, []):
            cx = positions[child][0]
            if child in on_path:
                style = f'stroke="{SOLUTION_COLOR}" stroke-width="3"'
            else:
                style = 'stroke="#888" stroke-width="1"'
            parts.append(f'<line x1="{px:g}" y1="{y1:g}" x2="{cx:g}" y2="{y2:g}" {style}/>')
    for node in nodes:
        x, depth = positions[node]
        svg, width, height = drawings[node]
        y = top(depth)
        expanded = node in number
        tooltip = [f"depth {depth}"]
        if node.action is not None:
            tooltip.append(str(node.action))
        tooltip.append(f"expanded as #{number[node]}" if expanded else "not expanded")
        opacity = '' if expanded or node in on_path or not fade else ' opacity="0.35"'
        parts.append(f'<g{opacity}><title>{escape(chr(10).join(tooltip))}</title>')
        if labels[node]:
            parts.append(f'<text x="{x:g}" y="{y - 4:g}" text-anchor="middle" '
                         f'font-size="{FONT_SIZE}">{escape(labels[node])}</text>')
        parts.append(f'<g transform="translate({x - width / 2:g},{y:g})">{svg}</g>')
        if node is solution:
            parts.append(f'<rect x="{x - width / 2 - 3:g}" y="{y - 3:g}" '
                         f'width="{width + 6:g}" height="{height + 6:g}" fill="none" '
                         f'stroke="{SOLUTION_COLOR}" stroke-width="3"/>')
        if expanded:
            parts.append(f'<text x="{x:g}" y="{y + height + TEXT_HEIGHT - 2:g}" '
                         f'text-anchor="middle" font-size="{FONT_SIZE}">#{number[node]}</text>')
        parts.append('</g>')

    total_width = max(right_edge.values()) + MARGIN
    max_depth = max(depth for _, depth in positions.values())
    total_height = top(max_depth) + box_height + TEXT_HEIGHT + MARGIN
    return svg_document(''.join(parts), total_width, total_height)


def draw_search_tree(expansions: Iterable[tuple[Any, Iterable[Any]]],
                     draw_state: Callable[[Any, Any], tuple[str, float, float]],
                     edge_label: Callable[[Any], str] | None = str,
                     solution: Any = None,
                     max_nodes: int = 1000,
                     fade: bool = True):
    """
    Displays the search tree(s) explored by a search algorithm.
    See `search_tree_svg()` for the arguments.
    """
    show_svg(search_tree_svg(expansions, draw_state, edge_label, solution, max_nodes, fade))
