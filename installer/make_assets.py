"""Generate the SHARC brand assets used by the installer.

Outputs (in installer/assets/): sharc.ico (16-256 px), wizard_large*.bmp,
wizard_small*.bmp. Run: python installer/make_assets.py
"""
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "assets"
SS = 4  # supersampling factor

BG_TOP = (24, 34, 52)
BG_BOT = (10, 15, 26)
ACCENT = (74, 163, 242)
ACCENT_LIGHT = (140, 200, 255)
WHITE = (245, 248, 252)
GOLD = (244, 188, 48)


def _gradient(size, top, bottom):
    w, h = size
    col = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        col.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return col.resize((w, h))


def _hexagon(cx, cy, r, rot=math.pi / 6):
    return [(cx + r * math.cos(rot + k * math.pi / 3), cy + r * math.sin(rot + k * math.pi / 3))
            for k in range(6)]


def _mark(size, detail=True):
    """Return the RGBA SHARC mark (hexagon, signal arcs, orbit) on a transparent canvas."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = s / 2
    r = s * 0.34

    # hexagon: translucent glow + solid fill + outline
    hexa = _hexagon(cx, cy, r)
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).polygon(hexa, fill=ACCENT + (70,))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(s * 0.03)))
    d.polygon(hexa, fill=(22, 52, 92, 255))
    d.line(hexa + [hexa[0]], fill=ACCENT + (255,), width=max(int(s * 0.035), 2), joint="curve")

    # signal arcs radiating from the source point
    sx, sy = cx - r * 0.18, cy + r * 0.05
    for i in ((1, 2, 3) if detail else (1, 2)):
        rr = r * (0.26 + 0.19 * i)
        d.arc((sx - rr, sy - rr, sx + rr, sy + rr), start=-50, end=50,
              fill=ACCENT_LIGHT + (255,), width=max(int(s * 0.032), 2))
    d.ellipse((sx - r * 0.17, sy - r * 0.17, sx + r * 0.17, sy + r * 0.17), fill=WHITE + (255,))

    # orbit ellipse around the hexagon, with satellites
    orb = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    a, b = s * 0.46, s * 0.17
    ImageDraw.Draw(orb).ellipse((cx - a, cy - b, cx + a, cy + b), outline=ACCENT + (190,),
                                width=max(int(s * 0.02), 2))
    img.alpha_composite(orb.rotate(18, resample=Image.BICUBIC, center=(cx, cy)))
    d = ImageDraw.Draw(img)
    ang = math.radians(-18)
    px, py = a * math.cos(0.25), b * math.sin(0.25)
    px, py = (cx + px * math.cos(ang) - py * math.sin(ang),
              cy + px * math.sin(ang) + py * math.cos(ang))
    d.ellipse((px - s * 0.045, py - s * 0.045, px + s * 0.045, py + s * 0.045), fill=WHITE + (255,))
    if detail:
        gx, gy = s * 0.74, s * 0.80
        d.ellipse((gx - s * 0.05, gy - s * 0.05, gx + s * 0.05, gy + s * 0.05),
                  fill=GOLD + (255,), outline=ACCENT + (255,), width=max(int(s * 0.012), 1))
    return img.resize((size, size), Image.LANCZOS)


def make_icon(size, detail=True):
    """Rounded-square app icon: gradient background, thin highlight border, the mark."""
    s = size * SS
    bg = _gradient((s, s), BG_TOP, BG_BOT).convert("RGBA")
    radius = int(s * 0.22)
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=radius, fill=255)

    edge = max(int(s * 0.012), 1)
    border = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle((edge, edge, s - 1 - edge, s - 1 - edge), radius=radius,
                                             outline=(255, 255, 255, 38), width=edge)
    bg.alpha_composite(border)
    bg.alpha_composite(_mark(size, detail).resize((s, s), Image.LANCZOS))
    bg.putalpha(ImageChops.multiply(bg.getchannel("A"), mask))
    return bg.resize((size, size), Image.LANCZOS)


def _font(px, bold=False):
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except OSError:
            continue
    return ImageFont.load_default()


def make_wizard_large(w, h):
    """Left panel of the Welcome/Finish pages."""
    img = _gradient((w, h), (22, 36, 60), (8, 12, 22)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    step = w * 0.28
    for row in range(-1, int(h / (step * 0.87)) + 2):
        for col in range(-1, 5):
            x = col * step * 1.5
            y = row * step * 0.87 * 2 + (step * 0.87 if col % 2 else 0)
            pts = _hexagon(x, y, step * 0.5, 0)
            d.line(pts + [pts[0]], fill=ACCENT + (16,), width=1)
    icon = make_icon(int(w * 0.62))
    top = int(h * 0.14)
    img.alpha_composite(icon, ((w - icon.width) // 2, top))
    d = ImageDraw.Draw(img)
    f1, f2 = _font(int(w * 0.20), True), _font(int(w * 0.075))
    ty = top + icon.height + int(h * 0.05)
    d.text(((w - d.textlength("SHARC", font=f1)) / 2, ty), "SHARC", font=f1, fill=WHITE)
    for i, line in enumerate(("Spectrum sharing and", "compatibility simulator")):
        d.text(((w - d.textlength(line, font=f2)) / 2, ty + w * 0.26 + i * w * 0.10), line,
               font=f2, fill=(160, 180, 205))
    d.rectangle((0, 0, 2, h), fill=ACCENT + (255,))
    return img.convert("RGB")


def make_wizard_small(s):
    """Header badge on the inner wizard pages (white background)."""
    base = Image.new("RGBA", (s, s), (255, 255, 255, 255))
    icon = make_icon(int(s * 0.92))
    base.alpha_composite(icon, ((s - icon.width) // 2, (s - icon.height) // 2))
    return base.convert("RGB")


def main():
    OUT.mkdir(exist_ok=True)
    sizes = (16, 20, 24, 32, 40, 48, 64, 128, 256)
    frames = [make_icon(sz, detail=sz >= 40) for sz in sizes]
    frames[-1].save(OUT / "sharc.ico", format="ICO", sizes=[(sz, sz) for sz in sizes],
                    append_images=frames[:-1])
    frames[-1].save(OUT / "sharc_256.png")
    make_icon(1024).save(OUT / "sharc_1024.png")
    # Inno Setup scale steps: 100%, 125%, 150%, 200%
    for tag, k in (("", 1.0), ("_125", 1.25), ("_150", 1.5), ("_200", 2.0)):
        make_wizard_large(int(164 * k), int(314 * k)).save(OUT / f"wizard_large{tag}.bmp")
        make_wizard_small(int(55 * k)).save(OUT / f"wizard_small{tag}.bmp")
    print("assets written to", OUT)


if __name__ == "__main__":
    main()
