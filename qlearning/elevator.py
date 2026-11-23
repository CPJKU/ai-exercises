"""
Elevator simulation module.

Function:
The car always has a direction of travel. It sweeps that way, serving the calls
that way to go the same way, and only turns around deliberately. We are modeling
the elevator `panel`: a floor shows an up lamp and a down lamp, the cabin shows
floor buttons.
"""
import itertools
import random
import math

N_FLOORS = 5    # floors are numbered 0..N_FLOORS-1
MAX_STEPS = 200 # give up on an episode after this many steps
GAMMA = 0.99    # discount factor

STOP, CONTINUE, REVERSE = 0, 1, 2
ACTIONS = (STOP, CONTINUE, REVERSE)
ACTION_NAMES = {STOP: "Stop", CONTINUE: "Continue", REVERSE: "Reverse"}

GOING_UP, GOING_DOWN = 0, 1
DIRECTION_NAMES = {GOING_UP: "Up", GOING_DOWN: "Down"}

WAIT_WEIGHT = 1.0
RIDE_WEIGHT = 1.0


def has_up_button(floor: int) -> bool:
    """ Every floor but the top has an up button. """
    return floor < N_FLOORS - 1


def has_down_button(floor: int) -> bool:
    """ Every floor but the bottom has a down button. """
    return floor > 0


def destinations(floor: int, going_up: bool) -> list[int]:
    """ Return the floors that can be requested from this floor. """
    if going_up:
        return list(range(floor + 1, N_FLOORS))
    else:
        return list(range(0, floor))


def settle(floor: int, direction: int) -> int:
    """
    The car cannot be heading out of the shaft: at the bottom it is going up,
    at the top it is going down. Here we flip the lift indicator on arrival.
    """
    if floor == 0:
        return GOING_UP
    elif floor == N_FLOORS - 1:
        return GOING_DOWN
    else:
        return direction


def all_states() -> list[tuple]:
    """
    Returns every state the panel can show. A state is (floor, direction, up, down, car), where
    up, down and car are each a tuple of N_FLOORS flags saying whether the lamp is lit.
    """
    ups = [lamps for lamps in itertools.product((0, 1), repeat=N_FLOORS)
           if all (has_up_button(f) or not lit for f, lit in enumerate(lamps))]
    downs = [lamps for lamps in itertools.product((0, 1), repeat=N_FLOORS)
             if all (has_down_button(f) or not lit for f, lit in enumerate(lamps))]
    cars = list(itertools.product((0, 1), repeat=N_FLOORS))
    return [(floor, direction, up, down, car)
            for floor in range(N_FLOORS)
            for direction in (GOING_UP, GOING_DOWN)
            if settle(floor, direction) == direction # no impossible pairs
            for up in ups
            for down in downs
            for car in cars]



def unfinished(state: tuple) -> int:
    """ Returns how many lamps are still lit: the elevator's measure of work left. """
    _, _, up, down, car = state
    return sum(up) + sum(down) + sum(car)


STATES = all_states()
START_STATES = [state for state in STATES if unfinished(state) > 0]



def anything_ahead(state: tuple) -> bool:
    """ Is there still a lit lamp further along the direction we are travelling? """
    floor, direction, up, down, car = state
    beyond = (range(floor + 1, N_FLOORS) if direction == GOING_UP else range(0, floor))
    return any(up[f] or down[f] or car[f] for f in beyond)


def step_cost(state: tuple, action: int) -> float:
    """
    Returns what taking `action` in this state costs us. The rewards is its
    negative, so an agent maximising reward is one that clears the lamps fast.
    
    """
    _, _, up, down, car = state
    wait = sum(up) + sum(down)
    ride = sum(car)
    return WAIT_WEIGHT * wait + RIDE_WEIGHT * ride


def set_weights(wait: float = 1.0, ride: float = 1.0) -> None:
    """
    Set the weights used in the step_cost function. The default is to weight
    waiting and riding equally.
    """
    global WAIT_WEIGHT, RIDE_WEIGHT
    WAIT_WEIGHT = wait
    RIDE_WEIGHT = ride


def make_destination_probability(options, weight_fn=None) -> callable:
    """
    Returns a function probability(dest) over eligible destinations.
    When a passenger boards, they press a button for one of the eligible destinations
    and this destination is chosen randomly according to the weighting function.

    Without weight_fn, all eligible destinations are equally likely.
    Otherwise, weight_fn(dest) supplies a nonnegative relative weight.
    """
    options = tuple(options)
    if not options:
        raise ValueError("No eligible destinations")

    if weight_fn is None:
        weight_fn = lambda dest: 1.0

    weights = {dest: float(weight_fn(dest)) for dest in options}

    if any(not math.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("Weights must be finite and nonnegative")

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("The total weights cannot be 0 or negative")

    probabilities = {
        dest: weight / total
        for dest, weight in weights.items()
    }

    return lambda dest: probabilities.get(dest, 0.0)



def transitions(state: tuple, action: int, create_dest_prob: callable = make_destination_probability) -> list[tuple]:
    """
    Returns the next possible states and their probabilities, given the current state and action.

    `Continue` and `Reverse` are certain, but `Stop` is not: whoever boards presses a button
    we cannot predict. The `floor_sampler` function is used to sample the buttons pressed by the passengers.
    """
    floor, direction, up, down, car = state

    if action == REVERSE:
        turned = GOING_DOWN if direction == GOING_UP else GOING_UP
        # at either end of the shaft there is nothing to turn towards so this just burns a tick
        return [(1.0, (floor, settle(floor, turned), up, down, car))]

    if action == CONTINUE:
        moved = floor + 1 if direction == GOING_UP else floor - 1
        return [(1.0, (moved, settle(moved, direction), up, down, car))]

    # action == STOP
    car = list(car)
    car[floor] = 0      # riders for this floor get out
    going_up = direction == GOING_UP
    lamps = list(up if going_up else down)
    if not lamps[floor]:
        # no one is waiting to get on, so we just burn a tick
        return [(1.0, (floor, settle(floor, direction), up, down, tuple(car)))]

    lamps[floor] = 0    # the lamp for this floor goes out, somebody boards
    options = destinations(floor, going_up)
    dest_probability = create_dest_prob(options)
    outcomes = {}
    for dest in options:
        buttons = list(car)
        buttons[dest] = 1
        key = ((floor, direction, tuple(lamps), down, tuple(buttons)) if going_up
               else (floor, direction, up, tuple(lamps), tuple(buttons)))
        outcomes[key] = outcomes.get(key, 0.0) + dest_probability(dest)
    return [(prob, state) for state, prob in outcomes.items()]


class Elevator:
    """
    The elevator problem as an environment to interact with.
    """

    def __init__(self, seed: int = 0):
        self.random = random.Random(seed)
        self.state = None

    def reset(self, state=None):
        """
        Starts a new episode, by default from a uniformly sampled state.
        """
        if state is None:
            state = self.random.choice(START_STATES)
        self.state = state
        return self.state

    def step(self, action: int):
        """
        Applies an action and returns (next_state, reward, done).
        """
        reward = -step_cost(self.state, action)
        outcomes = transitions(self.state, action)
        chances = [chance for chance, _ in outcomes]
        self.state = self.random.choices([s for _, s in outcomes], weights=chances)[0]
        return self.state, reward, unfinished(self.state) == 0

