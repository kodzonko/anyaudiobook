"""Widgets shared by the TUI's screens."""

import time
from collections.abc import Sequence
from typing import ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import OptionList
from textual.widgets.option_list import Option

CHOSEN_MARK = "●"
"""Marks the chosen entry of a :class:`ChoiceList`."""


class ChoiceList(OptionList):
    """A list to choose one value from.

    Up and down (and page up/down, home, end) move the highlight; enter or
    space choose the highlighted entry, which is then marked with
    :data:`CHOSEN_MARK`. Typing jumps to the first entry starting with what
    was typed. One entry is always chosen once there are any.
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("space", "select", "Choose", show=False)
    ]

    TYPE_AHEAD_SECONDS = 1.0
    """Keys typed within this long of each other search together."""

    class Chosen(Message):
        """The user chose an entry with enter or space."""

        def __init__(self, choice_list: ChoiceList, value: str) -> None:
            """Report that ``value`` was chosen in ``choice_list``."""
            super().__init__()
            self.choice_list = choice_list
            self.value = value

        @property
        def control(self) -> ChoiceList:
            """The list the choice was made in, for ``@on(..., selector)``."""
            return self.choice_list

    def __init__(self, *, placeholder: str = "", id: str | None = None) -> None:
        """Create an empty list showing ``placeholder`` until it has choices."""
        super().__init__(id=id)
        self.placeholder = placeholder
        self.value: str | None = None
        """The chosen entry's value, None while there are no entries."""
        self._values: list[str] = []
        self._labels: list[str] = []
        self._typed = ""
        self._typed_at = 0.0

    def on_mount(self) -> None:
        """Show the placeholder until :meth:`set_choices` is called."""
        if not self._values:
            self._show_placeholder()

    def set_choices(
        self, choices: Sequence[tuple[str, str]], value: str | None = None
    ) -> None:
        """Offer ``choices``, ``(value, label)`` pairs, with ``value`` chosen.

        The first entry is chosen when ``value`` is not among them. Offering
        the same entries again only changes the choice, so the highlight
        does not jump while the user is moving it.
        """
        values = [entry for entry, _ in choices]
        labels = [label for _, label in choices]
        chosen = value if value in values else next(iter(values), None)
        if values == self._values and labels == self._labels:
            self._mark(chosen)
            return
        self._values, self._labels, self.value = values, labels, chosen
        if not values:
            self._show_placeholder()
            return
        self.set_options(Option(self._prompt(index)) for index in range(len(values)))
        self.highlighted = values.index(chosen) if chosen is not None else 0

    def choose(self, value: str) -> None:
        """Choose and highlight ``value``, as if the user had."""
        if value in self._values:
            self._mark(value)
            self.highlighted = self._values.index(value)

    def _mark(self, value: str | None) -> None:
        """Move the chosen mark to ``value``."""
        previous, self.value = self.value, value
        for entry in {previous, value}:
            if entry in self._values:
                index = self._values.index(entry)
                self.replace_option_prompt_at_index(index, self._prompt(index))

    def _prompt(self, index: int) -> Content:
        """The text of entry ``index``, marked if it is the chosen one."""
        mark = CHOSEN_MARK if self._values[index] == self.value else " "
        return Content(f"{mark} {self._labels[index]}")

    def _show_placeholder(self) -> None:
        """Show the placeholder as a disabled entry."""
        self.set_options([Option(Content(self.placeholder), disabled=True)])

    @on(OptionList.OptionSelected)
    def _chosen(self, event: OptionList.OptionSelected) -> None:
        """Turn the option list's selection into a :class:`Chosen` message."""
        event.stop()
        value = self._values[event.option_index]
        self._mark(value)
        self.post_message(self.Chosen(self, value))

    def on_key(self, event: events.Key) -> None:
        """Jump to the first entry starting with the keys typed."""
        character = event.character
        if not character or character == " " or not character.isprintable():
            return
        now = time.monotonic()
        if now - self._typed_at > self.TYPE_AHEAD_SECONDS:
            self._typed = ""
        self._typed += character.casefold()
        self._typed_at = now
        for index, label in enumerate(self._labels):
            if label.casefold().startswith(self._typed):
                self.highlighted = index
                break
        event.stop()
        event.prevent_default()


class Slider(Widget, can_focus=True):
    """A whole number chosen with left and right, drawn as a slider.

    ``◀ ──────┼━━━━●────── ▶ +20%``: the knob ``●`` sits between the
    minimum and maximum, ``┼`` marks zero, and the stretch between them is
    highlighted. Left and right move the knob by one step, as do clicks on
    the arrows; a click on the track moves it there. ``0`` resets the value
    to zero, and enter moves on to the next field, like in a form.
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "slider--track",
        "slider--fill",
        "slider--knob",
    }

    DEFAULT_CSS = """
    Slider {
        width: 1fr;
        height: 3;
        padding: 0 1;
        background: $surface;
        border: tall $border-blurred;

        &:focus {
            border: tall $border;
            background-tint: $foreground 5%;
        }
        & > .slider--track {
            color: $foreground 35%;
        }
        & > .slider--fill {
            color: $accent;
        }
        & > .slider--knob {
            color: $foreground;
            text-style: bold;
        }
        &:focus > .slider--knob {
            color: $accent;
        }
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("left", "step(-1)", "Less"),
        Binding("right", "step(1)", "More"),
        Binding("0", "reset", "Reset"),
        Binding("enter", "next", "Next", show=False),
    ]

    value: reactive[int] = reactive(0)
    """The chosen number, kept between the minimum and maximum."""

    def __init__(
        self,
        *,
        minimum: int,
        maximum: int,
        step: int = 1,
        unit: str = "",
        value: int = 0,
        id: str | None = None,
    ) -> None:
        """Create a slider from ``minimum`` to ``maximum`` showing ``value``.

        Args:
            minimum: The lowest value.
            maximum: The highest value.
            step: How far left, right and the arrows move the knob.
            unit: Written after the value, e.g. ``%``.
            value: The value to start with.
            id: The widget's id.
        """
        super().__init__(id=id)
        self.minimum = minimum
        self.maximum = maximum
        self.step = step
        self.unit = unit
        self.set_reactive(Slider.value, self.validate_value(value))

    def validate_value(self, value: int) -> int:
        """Keep the value between the minimum and the maximum."""
        return max(self.minimum, min(self.maximum, value))

    def describe(self, value: int) -> str:
        """Write ``value`` with its sign and unit, e.g. ``+20%``."""
        return f"{value:+d}{self.unit}"

    def action_step(self, steps: int) -> None:
        """Move the knob ``steps`` steps, to the left when negative."""
        self.value += steps * self.step

    def action_reset(self) -> None:
        """Set the value back to zero."""
        self.value = 0

    def action_next(self) -> None:
        """Move on to the next field."""
        self.screen.focus_next()

    def render(self) -> Content:
        """Draw the arrows, the track with its knob, and the value."""
        cells = self._track_cells()
        knob = self._cell_of(self.value, cells)
        zero = self._cell_of(self.validate_value(0), cells)
        low, high = sorted((knob, zero))
        track: list[tuple[str, str]] = []
        for cell in range(cells):
            if cell == knob:
                track.append(("●", ".slider--knob"))
            elif cell == zero:
                track.append(("┼", ".slider--track"))
            elif low < cell < high:
                track.append(("━", ".slider--fill"))
            else:
                track.append(("─", ".slider--track"))
        label = self.describe(self.value).rjust(self._label_width())
        return Content.assemble("◀ ", *track, " ▶ ", label)

    def on_click(self, event: events.Click) -> None:
        """Step with the arrows, or move the knob to the clicked place."""
        offset = event.get_content_offset(self)
        if offset is None:
            return
        cells = self._track_cells()
        cell = offset.x - 2  # after "◀ "
        if cell < 0:
            self.action_step(-1)
        elif cell >= cells:
            self.action_step(1)
        else:
            span = self.maximum - self.minimum
            fraction = cell / (cells - 1) if cells > 1 else 0
            steps = round(fraction * span / self.step)
            self.value = self.minimum + steps * self.step

    def _label_width(self) -> int:
        """Width of the value, the same for every value so the track keeps still."""
        return max(len(self.describe(self.minimum)), len(self.describe(self.maximum)))

    def _track_cells(self) -> int:
        """How many cells the track takes, between the arrows."""
        return max(self.content_size.width - len("◀  ▶ ") - self._label_width(), 2)

    def _cell_of(self, value: int, cells: int) -> int:
        """The track cell standing for ``value``."""
        span = self.maximum - self.minimum
        if span <= 0:
            return 0
        return round((value - self.minimum) * (cells - 1) / span)
