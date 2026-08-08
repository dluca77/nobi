"""Composite branded graphics onto the intro/outro character plates and
render them as pan/zoom clips. SDXL renders text badly, so the "NOBI WORLD"
logo, subscribe button, and next-episode box are drawn with PIL (Fredoka
font) as a clean transparent overlay, then animated as a whole with an
ffmpeg fade-in on top of the zoompan background -- not per-shot generated.

Usage:
    python build_intro_outro.py
"""
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
FONT_PATH = r"C:\Users\Isaak\nobi\production\fonts\Fredoka-Bold.ttf"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"

CANVAS_W, CANVAS_H = 2688, 1536
YELLOW = (255, 204, 0, 255)
BLUE = (32, 90, 220, 255)
WHITE = (255, 255, 255, 255)
RED = (255, 59, 48, 255)
DARK = (20, 20, 30, 220)


def font(size, weight="Bold"):
    f = ImageFont.truetype(FONT_PATH, size)
    f.set_variation_by_name(weight)
    return f


def draw_text_outline(draw, xy, text, fnt, fill, outline, outline_w, anchor="la"):
    x, y = xy
    for dx in range(-outline_w, outline_w + 1):
        for dy in range(-outline_w, outline_w + 1):
            if dx * dx + dy * dy <= outline_w * outline_w:
                draw.text((x + dx, y + dy), text, font=fnt, fill=outline, anchor=anchor)
    draw.text((x, y), text, font=fnt, fill=fill, anchor=anchor)


def rounded_rect(draw, box, radius, fill, outline=None, outline_w=0):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=outline_w)


def build_logo(dest_path):
    """Standalone NOBI WORLD logo card, blocky yellow/blue title text on a
    transparent background, used for both the intro overlay and as a
    reusable brand asset."""
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    f_nobi = font(280)
    f_world = font(150)
    cx = CANVAS_W // 2

    draw_text_outline(draw, (cx, 560), "NOBI", f_nobi, YELLOW, (20, 20, 30, 255), 14, anchor="mm")
    draw_text_outline(draw, (cx, 780), "W O R L D", f_world, WHITE, BLUE, 10, anchor="mm")

    f_tag = font(56, "Medium")
    draw_text_outline(draw, (cx, 900), "New Worlds. Big Adventures. Together!", f_tag, WHITE, (20, 20, 30, 255), 4, anchor="mm")

    canvas.save(dest_path)
    return dest_path


def build_outro_overlay(dest_path):
    canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # subscribe button
    btn_box = (1780, 260, 2560, 420)
    rounded_rect(draw, btn_box, 30, RED)
    bx, by = 1850, 340
    draw.ellipse((bx, by - 45, bx + 90, by + 45), fill=WHITE)
    draw.polygon([(bx + 30, by - 20), (bx + 30, by + 20), (bx + 65, by)], fill=RED)
    f_btn = font(70)
    draw.text((1980, 340), "SUBSCRIBE", font=f_btn, fill=WHITE, anchor="lm")

    # next episode box
    box2 = (1780, 500, 2560, 900)
    rounded_rect(draw, box2, 24, DARK, outline=YELLOW, outline_w=6)
    draw.polygon([(2120, 640), (2120, 740), (2210, 690)], fill=WHITE)
    f_next = font(48)
    draw.text((2170, 820), "NEXT EPISODE", font=f_next, fill=WHITE, anchor="mm")
    f_ep = font(38, "Medium")
    draw.text((2170, 870), "Aflevering 2 - binnenkort", font=f_ep, fill=(220, 220, 220, 255), anchor="mm")

    # small wordmark bottom-left
    f_logo = font(64)
    draw_text_outline(draw, (140, 1380), "NOBI WORLD", f_logo, YELLOW, (20, 20, 30, 255), 6, anchor="lm")

    canvas.save(dest_path)
    return dest_path


def animate_with_overlay(base_png, overlay_png, dest_mp4, duration, fade_in_at, fade_dur, zoom_expr):
    fps = 25
    d_frames = int(duration * fps)
    vf = (
        f"[0:v]scale=8000:-1,zoompan=z='{zoom_expr}':d={d_frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080:fps={fps},format=yuva420p[bg];"
        f"[1:v]scale=1920:1080[ov];"
        f"[ov]fade=t=in:st={fade_in_at}:d={fade_dur}:alpha=1[ovf];"
        f"[bg][ovf]overlay=0:0:format=auto"
    )
    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", base_png,
        "-loop", "1", "-i", overlay_png,
        "-filter_complex", vf,
        "-t", str(duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        dest_mp4,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    logo_path = os.path.join(OUT_DIR, "nobi_world_logo.png")
    build_logo(logo_path)
    print("saved", logo_path)

    outro_overlay_path = os.path.join(OUT_DIR, "_outro_overlay.png")
    build_outro_overlay(outro_overlay_path)
    print("saved", outro_overlay_path)

    animate_with_overlay(
        os.path.join(OUT_DIR, "s0-intro-nobi.png"),
        logo_path,
        os.path.join(OUT_DIR, "intro_titlecard.mp4"),
        duration=6.0, fade_in_at=0.8, fade_dur=0.6,
        zoom_expr="min(zoom+0.003,1.15)",
    )
    print("saved intro_titlecard.mp4")

    animate_with_overlay(
        os.path.join(OUT_DIR, "s7-outro-nobi.png"),
        outro_overlay_path,
        os.path.join(OUT_DIR, "outro_endscreen.mp4"),
        duration=8.0, fade_in_at=1.0, fade_dur=0.7,
        zoom_expr="min(zoom+0.0012,1.1)",
    )
    print("saved outro_endscreen.mp4")

    os.remove(outro_overlay_path)
