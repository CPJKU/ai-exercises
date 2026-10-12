"""
Sudoku puzzles as a search problem.

A state is a (partially filled) grid, an action fills a single empty cell with
a digit. Only digits that do not already appear in the same row, column or box
are offered as actions.
"""
from dataclasses import dataclass
from pathlib import Path

from drawing import draw_search_tree, show_svg, svg_document

SUDOKU_DIR = Path(__file__).parent / 'sudokus'

# box shape (rows, columns) for each supported grid size
BOX_SHAPES = {4: (2, 2), 6: (2, 3), 9: (3, 3)}

EMPTY = 0


@dataclass(frozen=True)
class SudokuState:
    """
    A sudoku grid, stored as a tuple of rows, with 0 marking empty cells.
    Immutable and hashable, so states can be stored in sets and dicts.
    """
    grid: tuple[tuple[int, ...], ...]

    @property
    def size(self) -> int:
        return len(self.grid)

    @property
    def box_shape(self) -> tuple[int, int]:
        return BOX_SHAPES[self.size]

    def candidates(self, row: int, col: int) -> list[int]:
        """
        Returns all digits that can be placed at the given cell without
        repeating a digit in the same row, column, or box.
        """
        box_rows, box_cols = self.box_shape
        top = row - row % box_rows
        left = col - col % box_cols
        used = set(self.grid[row])
        used.update(self.grid[r][col] for r in range(self.size))
        used.update(self.grid[r][c]
                    for r in range(top, top + box_rows)
                    for c in range(left, left + box_cols))
        return [digit for digit in range(1, self.size + 1) if digit not in used]

    def __str__(self) -> str:
        return '\n'.join(''.join(str(digit) if digit != EMPTY else '?'
                                 for digit in row)
                         for row in self.grid)


@dataclass(frozen=True)
class SudokuAction:
    """
    Places a digit at a cell (row and column are counted from 0).
    """
    row: int
    col: int
    digit: int

    def __str__(self) -> str:
        return f"put {self.digit} into row {self.row + 1}, column {self.col + 1}"


class SudokuProblem:
    """
    The state space of filling in a given sudoku.
    If `early_dead_end` is true-ish, sudoku states with at least one unfillable
    cell do not have any more successors.
    """
    def __init__(self, start: SudokuState, early_dead_end: bool = False):
        self.start = start
        self.early_dead_end = early_dead_end

    def get_start(self) -> SudokuState:
        return self.start

    def is_goal(self, state: SudokuState) -> bool:
        """
        Checks whether every row, column, and box contains each digit once.
        """
        digits = set(range(1, state.size + 1))
        box_rows, box_cols = state.box_shape
        rows = [set(row) for row in state.grid]
        cols = [set(col) for col in zip(*state.grid)]
        boxes = [{state.grid[r][c]
                  for r in range(top, top + box_rows)
                  for c in range(left, left + box_cols)}
                 for top in range(0, state.size, box_rows)
                 for left in range(0, state.size, box_cols)]
        return all(group == digits for group in rows + cols + boxes)

    def successors(self, state: SudokuState) -> list[tuple[SudokuAction, SudokuState]]:
        """
        For every empty cell, returns all valid digits to fill in, together
        with the resulting states (cells in row-major order, digits ascending).
        """
        result = []
        for row in range(state.size):
            for col in range(state.size):
                if state.grid[row][col] != EMPTY:
                    continue
                candidates = state.candidates(row, col)
                if not candidates and self.early_dead_end:
                    return []
                for digit in candidates:
                    new_row = state.grid[row][:col] + (digit,) + state.grid[row][col + 1:]
                    new_grid = state.grid[:row] + (new_row,) + state.grid[row + 1:]
                    result.append((SudokuAction(row, col, digit), SudokuState(new_grid)))
        return result


def load_sudoku(name: str, early_dead_end: bool = False) -> SudokuProblem:
    """
    Loads the sudoku stored in sudokus/<name>.txt, e.g., load_sudoku('easy/0').
    The file has one line per row, with '?' marking empty cells.
    If `early_dead_end` is true-ish, sudoku states with at least one unfillable
    cell do not have any more successors.
    """
    path = SUDOKU_DIR / f'{name}.txt'
    lines = [''.join(line.split()) for line in path.read_text().splitlines()]
    lines = [line for line in lines if line]
    size = len(lines)
    if size not in BOX_SHAPES:
        raise ValueError(f"{path}: unsupported sudoku size {size}, "
                         f"expected one of {sorted(BOX_SHAPES)}")
    grid = []
    for line in lines:
        if len(line) != size:
            raise ValueError(f"{path}: expected {size} cells per row, got {line!r}")
        row = tuple(EMPTY if char == '?' else int(char) for char in line)
        if any(not 0 <= digit <= size for digit in row):
            raise ValueError(f"{path}: digits must be between 1 and {size}, got {line!r}")
        grid.append(row)
    return SudokuProblem(SudokuState(tuple(grid)), early_dead_end=early_dead_end)


def sudoku_svg(state: SudokuState, action: SudokuAction | None = None,
               given: SudokuState | None = None, cellsize: float = 30) -> tuple[str, float, float]:
    """
    Returns SVG elements depicting a sudoku grid, along with their width and
    height. If `given` is a state, digits not given there are drawn in blue.
    The cell filled by `action` is highlighted.
    """
    n = state.size
    box_rows, box_cols = state.box_shape
    pad = 1  # room for the thick outer border
    size = n * cellsize + 2 * pad
    parts = [f'<rect x="{pad}" y="{pad}" width="{n * cellsize:g}" height="{n * cellsize:g}" fill="white"/>']
    if action is not None:
        parts.append(f'<rect x="{pad + action.col * cellsize:g}" y="{pad + action.row * cellsize:g}" '
                     f'width="{cellsize:g}" height="{cellsize:g}" fill="#ffe08a"/>')
    # thin lines between cells, then thick lines between boxes on top
    for thick in (False, True):
        style = 'stroke="black" stroke-width="2"' if thick else 'stroke="#bbb" stroke-width="1"'
        for i in range(1, n):
            y = pad + i * cellsize
            if (i % box_rows == 0) == thick:
                parts.append(f'<line x1="{pad}" y1="{y:g}" x2="{pad + n * cellsize:g}" y2="{y:g}" {style}/>')
            x = pad + i * cellsize
            if (i % box_cols == 0) == thick:
                parts.append(f'<line x1="{x:g}" y1="{pad}" x2="{x:g}" y2="{pad + n * cellsize:g}" {style}/>')
    parts.append(f'<rect x="{pad}" y="{pad}" width="{n * cellsize:g}" height="{n * cellsize:g}" '
                 f'fill="none" stroke="black" stroke-width="2"/>')
    for row in range(n):
        for col in range(n):
            digit = state.grid[row][col]
            if digit == EMPTY:
                continue
            is_given = given is None or given.grid[row][col] == digit
            parts.append(f'<text x="{pad + (col + 0.5) * cellsize:g}" y="{pad + (row + 0.5) * cellsize:g}" '
                         f'text-anchor="middle" dominant-baseline="central" '
                         f'font-size="{0.6 * cellsize:g}" fill="{"black" if is_given else "#1f5fbf"}">'
                         f'{digit}</text>')
    return ''.join(parts), size, size


def draw_sudoku(state: SudokuState, given: SudokuState | None = None, cellsize: float = 30):
    """
    Displays a sudoku grid. If `given` is a state, digits not given there are
    drawn in blue.
    """
    svg, width, height = sudoku_svg(state, given=given, cellsize=cellsize)
    show_svg(svg_document(svg, width, height))


def draw_sudoku_tree(expansions, solution=None, cellsize: float = 16, max_nodes: int = 1000,
                     fade: bool = True):
    """
    Displays the search tree(s) explored by a search algorithm on a sudoku.
    `expansions` lists the expanded nodes in order, each with its successor
    nodes, as pairs `(node, children)`. If `solution` is a node, the path
    leading to it is highlighted. Unless `fade` is False, nodes that were
    generated but never expanded are drawn faded. Hover over a node for details.
    """
    # find the start state to tell given digits from filled ones
    root = next(iter(expansions))[0]
    while root.parent is not None:
        root = root.parent
    draw_search_tree(expansions,
                     lambda state, action: sudoku_svg(state, action, root.state, cellsize),
                     edge_label=None, solution=solution, max_nodes=max_nodes, fade=fade)
