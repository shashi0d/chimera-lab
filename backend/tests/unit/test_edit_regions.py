"""Putting an edit back (app/agentapi/edit_regions.py): what is taken from the model, and what is kept."""

from __future__ import annotations

from PIL import Image, ImageDraw

from app.agentapi import edit_regions as R

W = 400


def canvas(colour=(255, 255, 255)) -> Image.Image:
    return Image.new("RGB", (W, W), colour)


def area(box: tuple[int, int, int, int]) -> Image.Image:
    m = Image.new("L", (W, W), 0)
    ImageDraw.Draw(m).rectangle(box, fill=255)
    return m


def test_the_new_part_comes_across_whole_even_past_the_brush_and_nothing_far_away_changes():
    original = canvas()
    edited = canvas()
    d = ImageDraw.Draw(edited)
    d.rectangle((100, 100, 200, 200), fill=(200, 30, 30))  # the new part: bigger than the brush
    d.line((150, 200, 150, 225), fill=(200, 30, 30), width=2)  # a thin tip just past it
    d.rectangle((360, 360, 390, 390), fill=(0, 0, 0))  # a change far away (drift): not taken
    brush = area((120, 120, 180, 180))
    out = R.blend(original, edited, R.change_mask(original, edited, brush, 0.1))
    assert out.getpixel((105, 105))[1] < 100  # beyond the brush, within reach: the model's part
    assert out.getpixel((150, 222))[1] < 200  # the thin tip survived
    assert out.getpixel((375, 375)) == (255, 255, 255)  # far away: the original
    assert out.getpixel((10, 10)) == (255, 255, 255)


def test_drift_measures_change_outside_the_area():
    original = canvas()
    same = canvas()
    other = canvas((0, 0, 0))
    a = area((100, 100, 200, 200))
    assert R.drift(original, same, a, 0.02) == 0
    assert R.drift(original, other, a, 0.02) > 0.9


def test_a_small_area_gets_a_close_up_and_a_large_one_does_not():
    small = R.crop_box(area((180, 180, 210, 210)))
    assert small is not None and small.side >= round(W * 0.28) and small.box[0] <= 180 and small.box[2] >= 210
    assert R.crop_box(area((20, 20, 380, 380))) is None
    edited = Image.new("RGB", (1024, 1024), (0, 128, 0))
    pasted = R.paste(canvas(), edited, small)
    assert pasted.getpixel((195, 195)) == (0, 128, 0) and pasted.getpixel((5, 5)) == (255, 255, 255)


def test_leftover_marks_are_detected():
    a = area((100, 100, 200, 200))
    magenta = canvas()
    ImageDraw.Draw(magenta).rectangle((100, 100, 200, 200), fill=(255, 0, 200))
    assert R.leftover_colour(magenta, a, (255, 0, 200)) > 0.9
    assert R.leftover_colour(canvas(), a, (255, 0, 200)) == 0
    original = canvas()
    guide = canvas()
    ImageDraw.Draw(guide).line((100, 150, 300, 150), fill=(230, 30, 30), width=8)
    strokes = Image.new("L", (W, W), 0)
    ImageDraw.Draw(strokes).line((100, 150, 300, 150), fill=255, width=8)
    assert R.leftover_strokes(original, guide, guide, strokes) > 0.9  # the model copied the line
    assert R.leftover_strokes(original, guide, original, strokes) == 0  # it didn't
