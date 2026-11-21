"""Build crisp Money Theory icons for Windows and the browser.

Run with ``python tools/build_app_icons.py`` after installing Pillow. The app
itself does not need Pillow; it uses the generated images in ``public``.
"""

from pathlib import Path
from io import BytesIO
import struct

from PIL import Image, ImageDraw, ImageOps


PUBLIC = Path(__file__).resolve().parents[1] / "public"
LAVENDER_TOP = "#d1c5ff"
LAVENDER_BOTTOM = "#a895f3"
INK = "#11172c"
MINT = "#168a79"


def small_icon():
    """Draw the 16-pixel mark on its actual pixel grid so it stays sharp."""
    image = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 15, 15), radius=3, fill=LAVENDER_TOP)
    # A small M needs fewer bends than the full vector mark.
    rows = (
        "...##......##...",
        "...###....###...",
        "...####..####...",
        "...##.####.##...",
        "...##..##..##...",
        "...##......##...",
        "...##......##...",
        "...##......##...",
        "...##......##...",
    )
    for y, row in enumerate(rows, start=3):
        for x, pixel in enumerate(row):
            if pixel == "#":
                draw.point((x, y), fill=INK)
    draw.rectangle((11, 2, 12, 3), fill=MINT)
    return image


def vector_icon(size):
    """Render the larger mark with smooth edges and a subtle lavender gradient."""
    scale = 3 if size <= 48 else 4
    edge = size * scale
    gradient = Image.linear_gradient("L").resize((edge, edge))
    color = ImageOps.colorize(gradient, LAVENDER_TOP, LAVENDER_BOTTOM).convert("RGBA")
    mask = Image.new("L", (edge, edge))
    draw_mask = ImageDraw.Draw(mask)
    inset = round(edge * 0.02)
    draw_mask.rounded_rectangle(
        (inset, inset, edge - 1 - inset, edge - 1 - inset),
        radius=round(edge * 0.25), fill=255,
    )
    image = Image.new("RGBA", (edge, edge))
    image.paste(color, (0, 0), mask)
    draw = ImageDraw.Draw(image)
    points = [(0.20, 0.73), (0.20, 0.28), (0.39, 0.60),
              (0.57, 0.27), (0.79, 0.59), (0.79, 0.28)]
    points = [(round(x * edge), round(y * edge)) for x, y in points]
    stroke = round(edge * 0.105)
    draw.line(points, fill=INK, width=stroke, joint="curve")
    for x, y in points:
        radius = stroke / 2
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=INK)
    x, y = round(edge * 0.79), round(edge * 0.28)
    radius = edge * 0.067
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=MINT)
    method = Image.Resampling.BOX if size <= 48 else Image.Resampling.LANCZOS
    return image.resize((size, size), method)


def main():
    icons = {size: small_icon() if size == 16 else vector_icon(size)
             for size in (16, 24, 32, 44, 48, 64, 128, 192, 256, 512)}
    for size in (44, 192, 512):
        icons[size].save(PUBLIC / f"money-theory-icon-{size}.png")
    icons[256].save(PUBLIC / "money-theory-icon.png")
    # Store each hand-tuned size in the ICO. Pillow's ICO save would resize
    # the largest image and lose the crisp 16-pixel drawing.
    ico_sizes = (16, 24, 32, 48, 64, 128, 256)
    images = []
    for size in ico_sizes:
        buffer = BytesIO()
        icons[size].save(buffer, format="PNG")
        images.append(buffer.getvalue())
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    offset = 6 + 16 * len(images)
    for size, data in zip(ico_sizes, images):
        entries += struct.pack("<BBBBHHII", size % 256, size % 256,
                               0, 0, 1, 32, len(data), offset)
        offset += len(data)
    ico = header + entries + b"".join(images)
    for name in ("favicon.ico", "money-theory.ico", "daywell.ico", "money-theory-mark.ico"):
        (PUBLIC / name).write_bytes(ico)


if __name__ == "__main__":
    main()
