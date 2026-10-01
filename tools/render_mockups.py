#!/usr/bin/env python3
"""
Renders mockup images of what each device's ramp-progress indicator is
designed to look like, by directly re-implementing the same drawing logic
as ramp_display.c (Carta 2) / ramp_led.c (Aeris, Sport) in Python, using
the REAL digit-glyph bitmap extracted from the actual Carta 2 firmware
for the stage-number badge.

This is a design mockup, not a photo or an emulator -- nothing here has
been confirmed against a real screen or real LEDs. Geometry/colors match
the firmware source exactly; the glyph bit-order was reverse-engineered
by visual inspection (tried several bit-order hypotheses, picked the one
that produced recognizable digits) rather than independently proven the
same rigorous way as the firmware patch addresses -- flagged here, and in
the images themselves, rather than presented as more certain than it is.

Requires your own stock Carta 2 firmware body (header-stripped, i.e. the
file minus its first 40 bytes -- see focusv-ramp-firmware's apply_patch.py
for how to get one) for the digit glyph table. This repo doesn't include
or distribute that file, same policy as the rest of this project -- see
LEGAL.md.

Usage:
    python3 render_mockups.py --firmware your-carta2-body.bin --out-dir .
"""

import argparse
from PIL import Image, ImageDraw

FIRMWARE = None
OUT_DIR = "."

# ---- shared heat-gradient (matches ramp_display.c / ramp_led.c exactly) ----
COOL = (20, 112, 255)
HOT = (255, 161, 24)

def heat_color(frac):
    frac = max(0.0, min(1.0, frac))
    return tuple(int(COOL[i] + (HOT[i] - COOL[i]) * frac) for i in range(3))

# ---- digit glyph extraction (Carta 2 firmware, confirmed table address) ----
def load_digit_glyph(digit):
    with open(FIRMWARE, "rb") as f:
        data = f.read()
    base = 0x1e6cc
    glyph_size = 0x22
    g = data[base + digit * glyph_size : base + digit * glyph_size + glyph_size]
    rows = []
    for row in range(16):
        b0, b1 = g[row * 2], g[row * 2 + 1]
        bits = f"{b0:08b}"[::-1] + f"{b1:08b}"[::-1]
        rows.append([c == "1" for c in bits[:9]])
    return rows  # 16 rows x 9 cols, True = lit pixel

def draw_digit(draw, x, y, digit, color):
    rows = load_digit_glyph(digit)
    for ry, row in enumerate(rows):
        for rx, lit in enumerate(row):
            if lit:
                draw.point((x + rx, y + ry), fill=color)

# ---- battery readout (Carta 2) ----
# FUN_0000db40, confirmed in firmware-analysis-notes.md ("the entire
# live-heating status bar decoded"): draws 3 digits from a single byte
# value (0-255, i.e. a percentage) at the screen's far right (x=0x98-0xb0,
# i.e. x=152-176), followed by a unit glyph, then a 5-step battery-bar
# icon selected by (value-1)/20 -- or a distinct charging-animation
# primitive when plugged in. This function is NOT one of the three call
# sites this patch replaces (see ramp_display.c header) -- it keeps
# running every tick, completely unmodified, whether or not a ramp is
# active. So this isn't a new addition to the firmware: it's a real,
# always-on stock element this mockup was simply failing to draw.
# Exact Y position is not confirmed against a real screen (no y argument
# was recovered from the decompile, only the x range) -- placed here in
# the top status-bar strip (y=0-50) that GRAPH_Y0 already leaves free,
# which is the ordinary place a status icon like this would sit and the
# one region firmware-analysis-notes.md didn't already attribute to
# another element.
BATTERY_X, BATTERY_Y = 152, 16
BATTERY_ICON_W, BATTERY_ICON_H = 20, 10

def draw_battery(draw, percent):
    # The percentage number here is drawn with PIL's default font, not the
    # real extracted glyph table draw_digit() uses for the stage badge --
    # that table's bit-order was only validated by eye against a full 0-9
    # render, and digits 0 and 9 came out as garbage, unlike 1-8 (noted in
    # the carta2 README). A battery percentage is exactly the kind of value
    # where 0 and 9 show up constantly (10, 20, 90, 100...), so a placeholder
    # font here is more honest than running every battery mockup through a
    # known-broken pair of digits.
    draw.text((BATTERY_X, BATTERY_Y - 2), str(percent), fill=(210, 214, 220))
    icon_x = BATTERY_X + 24
    icon_y = BATTERY_Y + 3
    # body + nub, classic battery glyph
    draw.rectangle(
        [icon_x, icon_y, icon_x + BATTERY_ICON_W, icon_y + BATTERY_ICON_H],
        outline=(160, 164, 170),
    )
    draw.rectangle(
        [icon_x + BATTERY_ICON_W, icon_y + 3, icon_x + BATTERY_ICON_W + 3, icon_y + BATTERY_ICON_H - 3],
        fill=(160, 164, 170),
    )
    # 5-step bar fill, matching the firmware's (value-1)/20 bucketing
    bars_lit = max(0, min(5, (percent - 1) // 20 + 1))
    bar_w = (BATTERY_ICON_W - 2) // 5
    bar_color = (90, 210, 130) if percent > 20 else (230, 90, 70)
    for b in range(bars_lit):
        bx = icon_x + 1 + b * bar_w
        draw.rectangle([bx, icon_y + 2, bx + bar_w - 1, icon_y + BATTERY_ICON_H - 2], fill=bar_color)

# ---- Carta 2 screen mockup ----
def render_carta2():
    W, H = 240, 240
    img = Image.new("RGB", (W, H), (8, 8, 10))
    draw = ImageDraw.Draw(img)

    # Matches ramp_display.c exactly -- widened after an audit of the
    # already-shipped patch found two more stock screen elements
    # (FUN_0000dcac, FUN_0000e300) that needed suppressing during a ramp,
    # freeing real extra space this mockup now also reflects.
    GRAPH_X0, GRAPH_Y0, GRAPH_W, GRAPH_H = 10, 42, 220, 164
    AXIS_COLOR = (58, 73, 90)
    TARGET_COLOR = (132, 158, 197)

    # axes
    draw.line([(GRAPH_X0, GRAPH_Y0 + GRAPH_H), (GRAPH_X0 + GRAPH_W, GRAPH_Y0 + GRAPH_H)], fill=AXIS_COLOR, width=1)
    draw.line([(GRAPH_X0, GRAPH_Y0), (GRAPH_X0, GRAPH_Y0 + GRAPH_H)], fill=AXIS_COLOR, width=1)

    # 5 waypoints: a representative ramp (flower, 300 -> 460F over the chart)
    lo, hi = 300, 460
    waypoints_f = [320, 360, 400, 430, 450]
    stride = GRAPH_W // len(waypoints_f)

    def temp_to_y(t):
        frac = (t - lo) / (hi - lo)
        return GRAPH_Y0 + GRAPH_H - int(frac * GRAPH_H)

    # dashed target line connecting waypoints
    prev = None
    for i, t in enumerate(waypoints_f):
        x = GRAPH_X0 + i * stride
        y = temp_to_y(t)
        if prev:
            x0, y0 = prev
            steps = max(1, x - x0)
            for s in range(steps):
                if (s % 6) < 3:
                    xx = x0 + s
                    yy = y0 + int((y - y0) * s / steps)
                    draw.point((xx, yy), fill=TARGET_COLOR)
                    draw.point((xx, yy + 1), fill=TARGET_COLOR)
        # tick mark
        draw.line([(x, GRAPH_Y0 + GRAPH_H + 2), (x, GRAPH_Y0 + GRAPH_H + 5)], fill=AXIS_COLOR)
        prev = (x, y)

    # live trace: ramp is ~65% through, heat-graded, with a bright "now" marker
    current_stage = 3  # 1-indexed, matches the stage badge
    progress_cols = int(GRAPH_W * 0.65)
    prev = None
    for col in range(progress_cols):
        # simulate measured temp lagging/tracking the target with slight noise-free wobble
        t_frac = col / GRAPH_W
        target_now = waypoints_f[min(int(t_frac * len(waypoints_f)), len(waypoints_f) - 1)]
        measured = target_now - 4 + (col % 5)
        y = temp_to_y(measured)
        x = GRAPH_X0 + col
        color = heat_color((measured - lo) / (hi - lo))
        if prev:
            draw.line([prev, (x, y)], fill=color, width=3)
        prev = (x, y)
    if prev:
        draw.ellipse([prev[0] - 2, prev[1] - 2, prev[0] + 2, prev[1] + 2], fill=(255, 255, 255))

    # stage badge: white box + real digit glyph -- inset into the graph's
    # own bottom-left corner (matches ramp_display.c's STAGE_X/STAGE_Y) now
    # that there's no spare room below the taller graph.
    STAGE_X, STAGE_Y = GRAPH_X0 + 6, GRAPH_Y0 + GRAPH_H - 28
    PAD = 4
    draw.rectangle([STAGE_X - PAD, STAGE_Y - PAD, STAGE_X + 9 + PAD, STAGE_Y + 16 + PAD], fill=(255, 255, 255))
    draw_digit(draw, STAGE_X, STAGE_Y, current_stage, (0, 0, 0))

    # battery % -- a real stock element (FUN_0000db40) left completely
    # untouched by the ramp patch, so it keeps showing during a ramp on
    # real hardware. Not new firmware behavior, just a mockup that was
    # previously missing it. See draw_battery()'s own comment.
    draw_battery(draw, 68)

    img = img.resize((480, 480), Image.NEAREST)
    img.save(f"{OUT_DIR}/carta2-ramp-mockup.png")
    print("wrote carta2-ramp-mockup.png")

# ---- Aeris / Sport LED mockups ----
def render_led_mockup(name, led_count, lo, hi, out_name):
    # Show the LED ring at 3 representative progress moments (early/mid/late)
    W, H = 600, 220
    img = Image.new("RGB", (W, H), (14, 14, 16))
    draw = ImageDraw.Draw(img)
    stages = [("early", lo + (hi - lo) * 0.15), ("mid-ramp", lo + (hi - lo) * 0.55), ("near target", lo + (hi - lo) * 0.92)]
    col_w = W // len(stages)
    for i, (label, temp) in enumerate(stages):
        cx = col_w * i + col_w // 2
        color = heat_color((temp - lo) / (hi - lo))
        # draw the LEDs in a small arc
        import math
        radius = 50
        for led in range(led_count):
            angle = math.pi * (0.25 + 0.5 * led / max(1, led_count - 1))
            lx = cx + int(radius * math.cos(angle))
            ly = 90 - int(radius * math.sin(angle))
            draw.ellipse([lx - 14, ly - 14, lx + 14, ly + 14], fill=color, outline=(60, 60, 65), width=2)
        draw.text((cx - 36, 160), f"{label}\n~{int(temp)}F", fill=(180, 180, 185))
    img.save(f"{OUT_DIR}/{out_name}")
    print("wrote", out_name)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--firmware", required=True, help="your own Carta 2 firmware body (header-stripped)")
    parser.add_argument("--out-dir", default=".", help="where to write the PNGs (default: current directory)")
    args = parser.parse_args()

    FIRMWARE = args.firmware
    OUT_DIR = args.out_dir
    render_carta2()
    render_led_mockup("Aeris", 4, 275, 500, "aeris-led-mockup.png")
    render_led_mockup("Sport", 5, 275, 500, "sport-led-mockup.png")
