"""Widgets shared by the TUI's screens."""

import time
from collections.abc import Sequence
from typing import ClassVar

from textual import events, on
from textual.binding import Binding, BindingType
from textual.content import Content
from textual.message import Message
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
