"""
An interactive elevator you can press buttons on, driven by a learned controller.
"""
import random
import threading

import ipywidgets as widgets
from IPython.display import display

from .drawing import frame_svg
from .elevator import (ACTION_NAMES, ACTIONS, CONTINUE, GOING_DOWN, GOING_UP,
                      N_FLOORS, REVERSE, STOP, destinations, has_down_button,
                      has_up_button, settle)


class Playground:
    """
    A live elevator. Press the call buttons and watch the controller react.
    """

    def __init__(self, q_table: dict, controllers: dict, seed: int = 0):
        """
        `controllers` maps a name to a function from a state to an action. The one
        named 'learned' is also shown together with its Q-values.
        """
        self.q_table = q_table
        self.controllers = dict(controllers)
        self.random = random.Random(seed)
        self.reset()
        self._stop, self._thread = threading.Event(), None
        self._build()

    # ---- the world -------------------------------------------------------
    def reset(self):
        self.floor, self.tick, self.served, self.last = 0, 0, 0, None
        self.direction = GOING_UP
        self.up = [0] * N_FLOORS
        self.down = [0] * N_FLOORS
        self.car = [0] * N_FLOORS

    def press(self, floor: int, going_up: bool):
        (self.up if going_up else self.down)[floor] = 1

    def state(self):
        return (self.floor, self.direction, tuple(self.up), tuple(self.down),
                tuple(self.car))

    def outstanding(self) -> int:
        return sum(self.up) + sum(self.down) + sum(self.car)

    def advance(self):
        if self.outstanding():
            action = self.controllers[self.controller.value](self.state())
            going_up = self.direction == GOING_UP
            if action == REVERSE:
                turned = GOING_DOWN if going_up else GOING_UP
                self.direction = settle(self.floor, turned)
            elif action == CONTINUE:
                self.floor += 1 if going_up else -1
                self.direction = settle(self.floor, self.direction)
            else:
                if self.car[self.floor]:
                    self.served += 1
                    self.car[self.floor] = 0          # those passengers leave
                lamps = self.up if going_up else self.down
                if lamps[self.floor]:                 # only our way gets in
                    lamps[self.floor] = 0
                    # whoever boards presses a button, and we learn it now
                    self.car[self.random.choice(
                        destinations(self.floor, going_up))] = 1
            self.last = action
        self.tick += 1
        if self.arrivals.value and self.random.random() < 0.18:
            floor = self.random.randrange(N_FLOORS)
            options = ([True] if has_up_button(floor) else []) + \
                      ([False] if has_down_button(floor) else [])
            self.press(floor, self.random.choice(options))
        self.draw()

    # ---- drawing ---------------------------------------------------------
    def draw(self):
        """
        Renders one frame into the HTML widget.
        """
        for (floor, going_up), button in self.buttons.items():
            button.disabled = bool((self.up if going_up else self.down)[floor])

        state = self.state()
        values = (list(self.q_table[state])
                  if self.controller.value == 'learned' else None)
        caption = (f'tick {self.tick}   ·   delivered {self.served}   ·   '
                   f'lamps lit {self.outstanding()}   ·   '
                   f'sweeping {"up" if self.direction == GOING_UP else "down"}'
                   f'   ·   last action {ACTION_NAMES.get(self.last, "-")}')
        self.view.value = frame_svg(state, values, self.last, caption)

    # ---- controls --------------------------------------------------------
    def _build(self):
        self.view = widgets.HTML()
        self.controller = widgets.Dropdown(options=list(self.controllers),
                                           description='control')
        self.arrivals = widgets.Checkbox(value=False, description='random calls',
                                         indent=False)
        self.speed = widgets.IntSlider(value=420, min=120, max=1200, step=60,
                                       description='ms/tick')
        self.play = widgets.ToggleButton(description='Play', icon='play',
                                         button_style='success')
        step = widgets.Button(description='Step')
        reset = widgets.Button(description='Reset', button_style='warning')

        self.play.observe(self._toggle, names='value')
        self.controller.observe(lambda _: self.draw(), names='value')
        step.on_click(lambda _: self.play.value or self.advance())
        reset.on_click(lambda _: self._reset_click())

        self.buttons, rows = {}, []
        for floor in reversed(range(N_FLOORS)):
            row = []
            for going_up, symbol in ((True, '▲'), (False, '▼')):
                exists = has_up_button(floor) if going_up else has_down_button(floor)
                if not exists:
                    row.append(widgets.Label('', layout=widgets.Layout(width='70px')))
                    continue
                button = widgets.Button(description=f'F{floor} {symbol}',
                                        layout=widgets.Layout(width='70px'))
                button.on_click(self._presser(floor, going_up))
                self.buttons[(floor, going_up)] = button
                row.append(button)
            rows.append(widgets.HBox(row))

        self.panel = widgets.VBox([
            widgets.HBox([self.play, step, reset]),
            self.speed, self.controller, self.arrivals,
            widgets.HTML('<b>Call the elevator</b>'
                         '<br><i>a lamp stays lit until the lift stops there; ' \
                         'when a person enters the elevator, they press a random button inside</i>'),
            widgets.VBox(rows)])
        self.draw()

    def _presser(self, floor: int, going_up: bool):
        def handler(_):
            self.press(floor, going_up)
            self.draw()
        return handler

    def _reset_click(self):
        self.play.value = False          # also stops the thread, via _toggle
        self._stop.set()
        self.reset()
        self.draw()

    def _toggle(self, change):
        running = change['new']
        self.play.description = 'Pause' if running else 'Play'
        self.play.icon = 'pause' if running else 'play'
        if running:
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()
        else:
            self._stop.set()

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.advance()
            except Exception as error:               # never die silently
                self.view.value = f"<pre style='color:#c62828'>{error}</pre>"
                break
            self._stop.wait(self.speed.value / 1000)  # interruptible sleep

    def show(self):
        display(widgets.VBox([self.view, self.panel]))
