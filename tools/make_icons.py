"""Generate the app icons (needs Pillow): python tools/make_icons.py"""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "web" / "icons"
GREEN, DARK, LIGHT = (47, 125, 79), (37, 100, 63), (246, 248, 243)


def draw(size: int, pad: float) -> Image.Image:
    s = size * 4
    im = Image.new("RGBA", (s, s), GREEN + (255,))
    d = ImageDraw.Draw(im)
    inner = s * (1 - 2 * pad)
    ox = s * pad
    # three blades of grass
    for dx, h, lean in ((-0.22, 0.62, -0.10), (0.0, 0.85, 0.0), (0.22, 0.55, 0.10)):
        cx = ox + inner * (0.5 + dx)
        base = ox + inner * 0.95
        top = base - inner * h
        w = inner * 0.09
        d.polygon([(cx - w, base), (cx + w, base), (cx + inner * lean, top)], fill=LIGHT)
    d.ellipse([ox + inner * 0.12, ox + inner * 0.9, ox + inner * 0.88, ox + inner * 1.0], fill=DARK)
    return im.resize((size, size), Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draw(192, 0.14).save(OUT / "icon-192.png")
    draw(512, 0.14).save(OUT / "icon-512.png")
    draw(512, 0.26).save(OUT / "icon-maskable-512.png")  # extra padding: safe zone for masks
    draw(180, 0.14).save(OUT / "apple-touch-icon.png")
    draw(32, 0.10).save(OUT / "icon-32.png")
    print("icons written to", OUT)


if __name__ == "__main__":
    main()
