"""The process canvas, moved by hand - as smoothly as the architecture canvas.

Boxes on the business level used to be fixed: a press on one started a pan,
and every redraw refitted the view, so clicking a lane or a pool snapped the
diagram back to where it started. What is under test:

* a box follows the pointer, and moving it edits nothing - the model is the
  source, a hand-placed box is a reading aid;
* a box stays inside its own lane, because a box drawn in another lane would
  say someone else does the work, and that is the model's to state;
* a redraw of the same model keeps the reader's pan and zoom;
* a press that goes nowhere is still a click, so the one-meaning-per-box rule
  survives the drag.

Real input over the DevTools protocol: a synthetic MouseEvent is delivered to
whatever it names, and pointer capture is exactly what it would hide.
"""

from __future__ import annotations

import json
import time

import pytest

from test_canvas_interaction import (  # noqa: F401 - page and served are fixtures
    _back_to_business,
    _on_architecture,
    page,
    served,
)

pytestmark = pytest.mark.browser


def _fresh(loop, handle):
    """Back to the business level with no box moved by hand.

    The page is shared by every test in the module, and a box an earlier test
    moved can sit on top of the one this test means to press.
    """
    _back_to_business(loop, handle)
    loop.run_until_complete(handle.js(
        "window.PairAI.ProcessCanvas.forgetLayout(); "
        "window.PairAI.ProcessCanvas.render(window.PairAI.state.lastProcess); "
        "window.PairAI.ProcessCanvas.fit(); 1"))
    time.sleep(0.5)


def _clear_box(loop, handle, selector=".pc-activity:not(.refined)"):
    """A box to press: on screen, and actually what a press at that point hits."""
    return loop.run_until_complete(handle.js(f"""(() => {{
        const view = document.querySelector('#process-canvas').getBoundingClientRect();
        for (const group of document.querySelectorAll({json.dumps('#process-canvas ' + selector)})) {{
            const box = group.querySelector('.pc-box');
            if (!box) continue;
            const r = box.getBoundingClientRect();
            // Sampled: at fit scale a box can be 57px wide with its chip covering
            // most of it, so no fixed offset is reliably the box itself.
            for (let fy = 0.9; fy > 0.1; fy -= 0.1) {{
                for (let fx = 0.1; fx < 0.95; fx += 0.1) {{
                    const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
                    if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
                    const hit = document.elementFromPoint(x, y);
                    if (!hit || hit.closest('[data-node]') !== group) continue;
                    if (hit.closest('.pc-open, .pc-marker, .pc-port, .pc-edit, .pc-risk')) continue;
                    return {{ id: group.getAttribute('data-node'), x, y,
                              left: r.left, top: r.top, width: r.width, height: r.height }};
                }}
            }}
        }}
        return null;
    }})()"""))


def _where(loop, handle, node_id):
    return loop.run_until_complete(handle.js(f"""(() => {{
        const group = document.querySelector({json.dumps('[data-node=' + json.dumps(node_id) + ']')});
        const box = group && (group.querySelector('.pc-box') || group);
        if (!box) return null;
        const r = box.getBoundingClientRect();
        return {{ left: r.left, top: r.top, width: r.width, height: r.height }};
    }})()"""))


def _lane_of(loop, handle, node_id):
    """The screen band of the lane that contains this node's box."""
    return loop.run_until_complete(handle.js(f"""(() => {{
        const group = document.querySelector({json.dumps('[data-node=' + json.dumps(node_id) + ']')});
        const box = (group.querySelector('.pc-box') || group).getBoundingClientRect();
        const cy = box.top + box.height / 2;
        for (const lane of document.querySelectorAll('#process-canvas .pc-lane-box')) {{
            const r = lane.getBoundingClientRect();
            if (cy >= r.top && cy <= r.bottom && box.left >= r.left - 1) {{
                return {{ top: r.top, bottom: r.bottom }};
            }}
        }}
        return null;
    }})()"""))


def test_a_process_box_follows_the_pointer_and_edits_nothing(page) -> None:
    loop, handle = page
    _fresh(loop, handle)
    box = _clear_box(loop, handle)
    assert box, "no activity box on screen to move"
    before = loop.run_until_complete(handle.js("window.PairAI.Editor.getValue().length"))

    loop.run_until_complete(handle.drag(box["x"], box["y"], box["x"] + 120, box["y"]))
    time.sleep(0.4)
    after = _where(loop, handle, box["id"])
    assert after, "the box vanished during the drag"
    assert abs((after["left"] - box["left"]) - 120) < 30, (
        f"the box did not follow the pointer: moved {after['left'] - box['left']:.0f}px of 120"
    )
    assert loop.run_until_complete(handle.js("window.PairAI.Editor.getValue().length")) == before, (
        "moving a box edited the process - the layout is a reading aid, not a claim"
    )


def test_a_process_box_stays_inside_its_own_lane(page) -> None:
    """A box in another lane would say someone else does the work."""
    loop, handle = page
    _fresh(loop, handle)
    box = _clear_box(loop, handle)
    assert box, "no activity box on screen to move"
    lane = _lane_of(loop, handle, box["id"])
    assert lane, "the box is not inside a drawn lane, so there is no boundary to hold"

    # Hard upward, well past the top of the lane.
    loop.run_until_complete(handle.drag(box["x"], box["y"], box["x"], box["y"] - 600))
    time.sleep(0.4)
    after = _where(loop, handle, box["id"])
    still = _lane_of(loop, handle, box["id"])
    assert still and abs(still["top"] - lane["top"]) < 2, (
        "the box left its lane, or its lane moved to follow it out"
    )
    assert after["top"] >= still["top"] - 1, (
        f"the box was drawn above its lane: box top {after['top']:.0f}, lane top {still['top']:.0f}"
    )


def test_clicking_a_lane_keeps_the_readers_view(page) -> None:
    """Every redraw used to refit, so the diagram snapped back on any click."""
    loop, handle = page
    _fresh(loop, handle)
    # Pan somewhere first, over empty canvas below the diagram.
    empty = loop.run_until_complete(handle.js("""(() => {
        const r = document.querySelector('#process-canvas').getBoundingClientRect();
        return { x: Math.round(r.left + r.width * 0.5), y: Math.round(r.bottom - 30) };
    })()"""))
    loop.run_until_complete(handle.drag(empty["x"], empty["y"], empty["x"] + 80, empty["y"] - 40))
    time.sleep(0.4)
    panned = loop.run_until_complete(handle.js(
        'document.querySelector("#pc-root").getAttribute("transform")'))

    lane = loop.run_until_complete(handle.js("""(() => {
        // Sampled rather than assumed: flows, notes and boxes cross a lane.
        const view = document.querySelector('#process-canvas').getBoundingClientRect();
        for (const band of document.querySelectorAll('#process-canvas .pc-lane')) {
            const r = band.querySelector('.pc-lane-box').getBoundingClientRect();
            for (let fy = 0.15; fy < 0.95; fy += 0.1) {
                for (let fx = 0.2; fx < 0.98; fx += 0.06) {
                    const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
                    if (x < view.left || x > view.right || y < view.top || y > view.bottom) continue;
                    const hit = document.elementFromPoint(x, y);
                    if (hit && hit.classList.contains('pc-lane-box') && hit.closest('.pc-lane') === band) {
                        return { x, y };
                    }
                }
            }
        }
        return null;
    })()"""))
    assert lane, "no clear spot on a lane to click"
    loop.run_until_complete(handle.click(lane["x"], lane["y"]))
    time.sleep(0.6)
    assert loop.run_until_complete(handle.js(
        'document.querySelector("#pc-root").getAttribute("transform")')) == panned, (
        "clicking a lane snapped the view back - a redraw of the same model refitted it"
    )


def test_a_box_pressed_without_moving_still_opens(page) -> None:
    """Drag and click are one gesture, told apart by distance, so the rule that a
    box means one thing survives: pressed and released in place, it opens."""
    loop, handle = page
    _fresh(loop, handle)
    box = _clear_box(loop, handle)
    assert box, "no activity box on screen to press"
    loop.run_until_complete(handle.click(box["x"], box["y"]))
    time.sleep(0.6)
    opened = loop.run_until_complete(handle.js(
        '!document.querySelector("#process-detail").classList.contains("hidden")'))
    assert opened, "a plain press on a box no longer opens it"
    loop.run_until_complete(handle.js('document.querySelector("#process-detail").classList.add("hidden"); 1'))


def test_a_refined_box_moves_and_its_chip_still_descends(page) -> None:
    """The box of an AI activity moves like any other, and the chip on it is
    still the one way down - moving must not become a second meaning for it."""
    loop, handle = page
    _fresh(loop, handle)
    box = _clear_box(loop, handle, ".pc-activity.refined")
    assert box, "no refined activity box on screen"
    loop.run_until_complete(handle.drag(box["x"], box["y"], box["x"] + 60, box["y"]))
    time.sleep(0.4)
    assert not _on_architecture(loop, handle), "moving an AI activity descended into it"

    chip = loop.run_until_complete(handle.js(f"""(() => {{
        const group = document.querySelector({json.dumps('#process-canvas [data-node=' + json.dumps(box['id']) + ']')});
        if (!group) return {{ why: 'the box is gone from the canvas' }};
        const open = group.querySelector('.pc-open');
        if (!open) return {{ why: 'the box carries no chip after the move' }};
        const r = open.getBoundingClientRect();
        const x = Math.round(r.left + r.width / 2), y = Math.round(r.top + r.height / 2);
        // What a press there reaches, not what is drawn there.
        const hit = document.elementFromPoint(x, y);
        if (!hit || !hit.closest('.pc-open')) {{
            return {{ why: 'the chip is under '
                + (hit ? (hit.id || hit.getAttribute('class') || hit.tagName) : 'nothing') }};
        }}
        return {{ x, y }};
    }})()"""))
    assert chip.get("x") is not None, chip.get("why")
    loop.run_until_complete(handle.click(chip["x"], chip["y"]))
    time.sleep(0.8)
    assert _on_architecture(loop, handle), "after a move, the chip no longer opens the architecture"
    _back_to_business(loop, handle)
