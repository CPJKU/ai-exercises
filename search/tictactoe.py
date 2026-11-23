"""
Tic-tac-toe as a two-player game, for minimax and alpha-beta search.

A state is a string of nine characters, one for each cell, numbered row by row:

    0 | 1 | 2
    ---+---+---
    3 | 4 | 5
    ---+---+---
    6 | 7 | 8

Each character is "X", "O" or "." for an empty cell. X moves first and is the
MAX player, O is the MIN player.
"""

LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8),      # rows
         (0, 3, 6), (1, 4, 7), (2, 5, 8),      # columns
         (0, 4, 8), (2, 4, 6)]                 # diagonals


class TicTacToe:
    """
    The rules of tic-tac-toe.
    """

    def __init__(self):
        # how often successors() was called, to compare search algorithms
        self.expansions = 0

    def get_start(self) -> str:
        """
        Returns the empty board.
        """
        return "." * 9

    def winner(self, state: str) -> str | None:
        """
        Returns "X" or "O" if that player has three in a row, otherwise None.
        """
        for a, b, c in LINES:
            if state[a] != "." and state[a] == state[b] == state[c]:
                return state[a]
        return None

    def is_terminal(self, state: str) -> bool:
        """
        Returns whether the game is over: somebody has won, or the board is full.
        """
        return self.winner(state) is not None or "." not in state

    def utility(self, state: str) -> int:
        """
        Returns the result of a finished game from X's point of view:
        +1 if X has won, -1 if O has won, 0 for a draw.
        """
        if not self.is_terminal(state):
            raise ValueError("utility() is only defined for finished games")
        return {"X": 1, "O": -1, None: 0}[self.winner(state)]

    def is_max_turn(self, state: str) -> bool:
        """
        Returns whether it is X's (MAX's) turn, rather than O's (MIN's).
        """
        return state.count("X") == state.count("O")

    def result(self, state: str, action: int) -> str:
        """
        Returns the state after the player to move has played cell `action`.
        """
        player = "X" if self.is_max_turn(state) else "O"
        return state[:action] + player + state[action + 1:]

    def successors(self, state: str) -> list[tuple[int, str]]:
        """
        Returns all moves as (action, next state) pairs. The action is the
        number of the cell that gets played. A finished game has no moves.
        """
        self.expansions += 1
        if self.is_terminal(state):
            return []
        player = "X" if self.is_max_turn(state) else "O"
        return [(cell, state[:cell] + player + state[cell + 1:])
                for cell in range(9) if state[cell] == "."]


def print_board(state: str) -> None:
    """
    Prints a state as a 3x3 board.
    """
    rows = [" " + " | ".join(state[r * 3:r * 3 + 3]) for r in range(3)]
    print("\n---+---+---\n".join(rows))
