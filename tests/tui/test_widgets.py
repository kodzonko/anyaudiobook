"""Tests for the TUI's widgets, each in a small app of its own."""

import pytest
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Button

from anyaudiobook.tui.widgets import CHOSEN_MARK, ChoiceList, Slider

pytestmark = pytest.mark.anyio

FRUIT = [
    ("apple", "Apple"),
    ("banana", "Banana"),
    ("blueberry", "Blueberry"),
    ("cherry", "Cherry"),
]


class ListApp(App[None]):
    """One focused ChoiceList, recording what is chosen."""

    def __init__(self) -> None:
        """Start with nothing chosen."""
        super().__init__()
        self.chosen: list[str] = []

    def compose(self) -> ComposeResult:
        """Just the list."""
        yield ChoiceList(placeholder="Nothing yet", id="fruit")

    @on(ChoiceList.Chosen)
    def record(self, event: ChoiceList.Chosen) -> None:
        """Remember the choice."""
        self.chosen.append(event.value)


def prompts(choice_list: ChoiceList) -> list[str]:
    """The visible text of each entry."""
    return [
        str(choice_list.get_option_at_index(i).prompt)
        for i in range(choice_list.option_count)
    ]


async def test_choice_list_shows_a_placeholder_until_it_has_choices() -> None:
    async with ListApp().run_test() as pilot:
        fruit = pilot.app.query_one(ChoiceList)

        assert prompts(fruit) == ["Nothing yet"]
        assert fruit.value is None


@pytest.mark.parametrize("key", ["enter", "space"])
async def test_choice_list_chooses_with_enter_or_space(key: str) -> None:
    app = ListApp()
    async with app.run_test() as pilot:
        fruit = app.query_one(ChoiceList)
        fruit.set_choices(FRUIT)
        fruit.focus()

        await pilot.press("down", "down", key)

        assert app.chosen == ["blueberry"]
        assert fruit.value == "blueberry"
        assert prompts(fruit)[2] == f"{CHOSEN_MARK} Blueberry"
        assert prompts(fruit)[0] == "  Apple"


async def test_choice_list_jumps_to_what_is_typed() -> None:
    app = ListApp()
    async with app.run_test() as pilot:
        fruit = app.query_one(ChoiceList)
        fruit.set_choices(FRUIT)
        fruit.focus()

        await pilot.press("b", "l")
        typed_two = fruit.highlighted
        await pilot.press("C")

        assert typed_two == 2  # "bl" -> Blueberry
        assert fruit.highlighted == 2  # "blc" matches nothing: stays
        fruit._typed_at = 0  # as if a second had passed
        await pilot.press("c")
        assert fruit.highlighted == 3
        assert app.chosen == []


async def test_choice_list_defaults_to_the_first_entry_and_keeps_the_highlight() -> (
    None
):
    app = ListApp()
    async with app.run_test() as pilot:
        fruit = app.query_one(ChoiceList)
        fruit.set_choices(FRUIT, "kiwi")
        fruit.focus()
        await pilot.press("down", "down", "down")

        fruit.set_choices(FRUIT, "banana")  # e.g. a refreshed list

        assert fruit.value == "banana"
        assert fruit.highlighted == 3
        fruit.set_choices([])
        assert fruit.value is None
        assert prompts(fruit) == ["Nothing yet"]


async def test_choice_list_choose_marks_and_highlights() -> None:
    app = ListApp()
    async with app.run_test():
        fruit = app.query_one(ChoiceList)
        fruit.set_choices(FRUIT)

        fruit.choose("cherry")
        fruit.choose("durian")

        assert (fruit.value, fruit.highlighted) == ("cherry", 3)
        assert app.chosen == []


class SliderApp(App[None]):
    """A speed slider at +10%, and a button after it."""

    def compose(self) -> ComposeResult:
        """The slider, then the button enter moves on to."""
        yield Slider(minimum=-50, maximum=100, step=5, unit="%", value=10)
        yield Button("Next")


SLIDER_SIZE = (40, 6)
"""The slider's content is 36 cells wide: 26 for its track, from x=4 on."""


async def test_slider_steps_with_left_and_right_within_its_range() -> None:
    app = SliderApp()
    async with app.run_test() as pilot:
        slider = app.query_one(Slider)
        slider.focus()

        await pilot.press("right", "right", "left")
        assert slider.value == 15
        await pilot.press(*["right"] * 30)
        assert slider.value == 100
        await pilot.press("0")
        assert slider.value == 0
        await pilot.press(*["left"] * 30)
        assert slider.value == -50

        await pilot.press("enter")
        assert app.focused is app.query_one(Button)


async def test_slider_draws_its_value_on_a_track_from_zero() -> None:
    app = SliderApp()
    async with app.run_test(size=SLIDER_SIZE):
        slider = app.query_one(Slider)

        text = str(slider.render())
        track = text.removeprefix("◀ ").removesuffix(" ▶  +10%")

        assert len(track) == 26
        assert track == "────────┼━●───────────────"  # 0 at 8, +10 at 10
        slider.value = -50
        assert str(slider.render()).startswith("◀ ●━━━━━━━┼")


@pytest.mark.parametrize(
    ("x", "value"),
    [(2, 5), (4, -50), (4 + 8, 0), (4 + 25, 100), (31, 15)],
    ids=["left arrow", "track start", "track at zero", "track end", "right arrow"],
)
async def test_slider_follows_clicks(x: int, value: int) -> None:
    app = SliderApp()
    async with app.run_test(size=SLIDER_SIZE) as pilot:
        await pilot.click(Slider, offset=(x, 1))

        assert app.query_one(Slider).value == value
        assert app.focused is app.query_one(Slider)
