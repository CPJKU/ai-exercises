"""
Sliding-tile puzzles (8-puzzle, 15-puzzle) as a search problem.

A state is a board, an action slides one tile into the empty space. Every
move costs 1, so the cost of a solution is the number of moves.
"""
import random
from dataclasses import dataclass

from drawing import draw_search_tree, show_svg, svg_document

EMPTY = 0


@dataclass(frozen=True)
class PuzzleState:
    """
    A board of size x size cells, stored row by row as a tuple of tile numbers
    with 0 marking the empty space. Immutable and hashable, so states can be
    stored in sets and dicts.
    """
    tiles: tuple[int, ...]
    size: int

    def position(self, tile: int) -> tuple[int, int]:
        """
        Returns the (row, column) of a tile on the board.
        """
        return divmod(self.tiles.index(tile), self.size)

    def __str__(self) -> str:
        width = len(str(self.size ** 2 - 1))
        return '\n'.join(' '.join(f"{tile if tile != EMPTY else '.':>{width}}"
                                  for tile in self.tiles[row * self.size:(row + 1) * self.size])
                         for row in range(self.size))


@dataclass(frozen=True)
class PuzzleAction:
    """
    Slides a tile into the empty space; the tile is moving up, down, left, or right.
    """
    direction: str
    tile: int
    cost: float = 1

    def __str__(self) -> str:
        return f"move {self.tile} {self.direction}"


MOVES = {'up': (-1, 0), 'down': (1, 0), 'left': (0, -1), 'right': (0, 1)}


class PuzzleProblem:
    """
    The state space of sorting a sliding-tile puzzle: tiles 1, 2, ... in
    reading order, with the empty space in the bottom right corner.
    """
    def __init__(self, start: PuzzleState):
        self.start = start
        n = start.size
        self.goal = PuzzleState(tuple(range(1, n * n)) + (EMPTY,), n)

    def get_start(self) -> PuzzleState:
        return self.start

    def is_goal(self, state: PuzzleState) -> bool:
        return state == self.goal

    def successors(self, state: PuzzleState) -> list[tuple[PuzzleAction, PuzzleState]]:
        """
        Returns all tiles next to the empty space, slid into it. The tile that
        slides in moves in the opposite direction of the empty space.
        """
        n = state.size
        blank = state.tiles.index(EMPTY)
        row, col = divmod(blank, n)
        result = []
        # the empty space moves up/down/left/right, so the tile moves the other way
        for direction, opposite in (('down', 'up'), ('up', 'down'), ('right', 'left'), ('left', 'right')):
            d_row, d_col = MOVES[opposite]
            new_row, new_col = row + d_row, col + d_col
            if 0 <= new_row < n and 0 <= new_col < n:
                tiles = list(state.tiles)
                other = new_row * n + new_col
                tiles[blank], tiles[other] = tiles[other], tiles[blank]
                result.append((PuzzleAction(direction, state.tiles[other]),
                               PuzzleState(tuple(tiles), n)))
        return result


def scrambled_puzzle(size: int = 3, moves: int = 30, seed: int = 0) -> PuzzleProblem:
    """
    Returns a puzzle that was scrambled by making a number of random moves from
    the goal, without immediately undoing the last move. The same seed always
    gives the same puzzle. The shortest solution can be shorter than `moves`.
    """
    rng = random.Random(seed)
    problem = PuzzleProblem(PuzzleState(tuple(range(1, size * size)) + (EMPTY,), size))
    state, previous = problem.goal, None
    for _ in range(moves):
        options = [new_state for _, new_state in problem.successors(state) if new_state != previous]
        previous, state = state, rng.choice(options)
    return PuzzleProblem(state)


def puzzle_svg(state: PuzzleState, action: PuzzleAction | None = None,
               cellsize: float = 40) -> tuple[str, float, float]:
    """
    Returns SVG elements depicting a board, along with their width and
    height. The tile moved by `action` is highlighted.
    """
    n = state.size
    pad = 1
    size = n * cellsize + 2 * pad
    parts = [f'<rect x="{pad}" y="{pad}" width="{n * cellsize:g}" height="{n * cellsize:g}" fill="#eee" '
             f'stroke="black" stroke-width="2"/>']
    for i, tile in enumerate(state.tiles):
        if tile == EMPTY:
            continue
        row, col = divmod(i, n)
        x, y = pad + col * cellsize, pad + row * cellsize
        highlighted = action is not None and action.tile == tile
        parts.append(f'<rect x="{x + 2:g}" y="{y + 2:g}" width="{cellsize - 4:g}" height="{cellsize - 4:g}" '
                     f'rx="4" fill="{"#ffe08a" if highlighted else "white"}" stroke="#888"/>'
                     f'<text x="{x + cellsize / 2:g}" y="{y + cellsize / 2:g}" text-anchor="middle" '
                     f'dominant-baseline="central" font-size="{0.45 * cellsize:g}">{tile}</text>')
    return ''.join(parts), size, size


def draw_puzzle(state: PuzzleState, cellsize: float = 40):
    """
    Displays a board.
    """
    svg, width, height = puzzle_svg(state, cellsize=cellsize)
    show_svg(svg_document(svg, width, height))


def draw_puzzle_solution(node, cellsize: float = 30):
    """
    Displays all boards on the way from the start to the given search node,
    side by side, with the tile moved in each step highlighted.
    """
    steps = []
    while node is not None:
        steps.insert(0, node)
        node = node.parent
    gap, x, parts, height = 12, 0, [], 0
    for step in steps:
        svg, w, h = puzzle_svg(step.state, step.action, cellsize)
        parts.append(f'<g transform="translate({x:g},0)">{svg}</g>')
        x += w + gap
        height = max(height, h)
    show_svg(svg_document(''.join(parts), x, height))
