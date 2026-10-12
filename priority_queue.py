import heapq
from typing import Any, Iterator


class PriorityQueue:
    """
    Instantiates an empty priority queue.
    """
    def __init__(self):
        self.insertion = 0
        self.heap = []

    """
    Adds an element of the given priority.
    """
    def push(self, value: Any, priority: float):
        heapq.heappush(self.heap, (priority, self.insertion, value))
        self.insertion += 1

    """
    Removes and returns the element of the lowest priority. If multiple
    elements have the same lowest priority, returns the one inserted first.
    """
    def pop(self) -> Any:
        _, _, value = heapq.heappop(self.heap)
        return value

    def __iter__(self) -> Iterator[Any]:
        return iter(value for _, _, value in self.heap)

    def __repr__(self) -> str:
        return ('PriorityQueue([' + ', '.join(repr(value) for value in self) + '])')

    def __len__(self) -> int:
        return len(self.heap)
