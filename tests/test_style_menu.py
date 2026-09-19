import cv2
import numpy as np
import pytest

from handyband.display import StyleMenu


@pytest.mark.parametrize("width", [640, 1280])
def test_menu_opens_at_top_right_and_selection_closes_it(width: int) -> None:
    menu = StyleMenu(("Odysseus", "Piano"), "Odysseus")
    frame = np.zeros((480, width, 3), dtype=np.uint8)
    menu.draw(frame)

    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, width - 50, 25, 0, None)
    assert menu.expanded
    menu.draw(frame)
    assert frame[50, width - 50].any()

    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, width - 50, 65, 0, None)
    assert not menu.expanded
    assert menu.style_name == "Odysseus"


def test_menu_ignores_motion_and_closes_on_outside_click() -> None:
    menu = StyleMenu(("Odysseus", "Piano"), "Odysseus")
    menu.draw(np.zeros((480, 640, 3), dtype=np.uint8))
    menu.on_mouse(cv2.EVENT_MOUSEMOVE, 590, 25, 0, None)
    assert not menu.expanded
    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, 590, 25, 0, None)
    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, 20, 200, 0, None)
    assert not menu.expanded


def test_menu_selects_piano_as_second_style() -> None:
    menu = StyleMenu(("Odysseus", "Piano"), "Odysseus")
    menu.draw(np.zeros((480, 640, 3), dtype=np.uint8))

    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, 590, 25, 0, None)
    menu.on_mouse(cv2.EVENT_LBUTTONDOWN, 590, 100, 0, None)

    assert not menu.expanded
    assert menu.style_name == "Piano"
