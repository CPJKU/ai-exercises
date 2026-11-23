"""
Tools for running and comparing controllers. A controller is a function that
gets the current state and returns an action.
"""
import random

from .elevator import Elevator, START_STATES, MAX_STEPS


def run_episode(controller, env, start=None, max_steps=MAX_STEPS):
    """
    Runs one episode and returns the states visited and the actions taken.
    """
    state = env.reset(start)
    states, actions = [state], []
    for _ in range(max_steps):
        action = controller(state)
        state, reward, done = env.step(action)
        states.append(state)
        actions.append(action)
        if done:
            break
    return states, actions


def average_cost(controller, episodes=1000, seed=999):
    """
    Returns the average total cost of clearing the building, and how often the
    controller managed it at all within the step limit.
    """
    chooser = random.Random(seed)
    env = Elevator(seed=seed)
    total, cleared = 0.0, 0
    for _ in range(episodes):
        state = env.reset(chooser.choice(START_STATES))
        for _ in range(MAX_STEPS):
            state, reward, done = env.step(controller(state))
            total -= reward
            if done:
                cleared += 1
                break
    return total / episodes, cleared / episodes
