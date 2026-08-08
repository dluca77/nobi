"""Build a single contact-sheet image from all Nobi-LoRA training images, for
visual QA of the dataset (e.g. checking every image really has a yellow block head).
"""
import os

from PIL import Image, ImageDraw, ImageFont

SRC_DIR = r"C:\Users\Isaak\kohya_ss\nobi_lora_dataset\img\5_nobi character"
DEST = r"C:\Users\Isaak\nobi\production\output\nobi_dataset_contactsheet.png"

COLS = 10
THUMB = 220
LABEL_H = 22
PAD = 6


def build_contactsheet(src_dir=SRC_DIR, dest=DEST, cols=COLS):
    files = sorted(f for f in os.listdir(src_dir) if f.lower().endswith(".png"))
    n = len(files)
    rows = (n + cols - 1) // cols

    cell_w = THUMB + PAD * 2
    cell_h = THUMB + LABEL_H + PAD * 2

    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (30, 30, 30))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 11)
    except Exception:
        font = ImageFont.load_default()

    for i, fname in enumerate(files):
        row, col = divmod(i, cols)
        x0, y0 = col * cell_w + PAD, row * cell_h + PAD
        img = Image.open(os.path.join(src_dir, fname)).convert("RGB")
        img.thumbnail((THUMB, THUMB), Image.LANCZOS)
        ox = x0 + (THUMB - img.width) // 2
        oy = y0 + (THUMB - img.height) // 2
        sheet.paste(img, (ox, oy))

        label = os.path.splitext(fname)[0]
        if len(label) > 26:
            label = label[:24] + "\u2026"
        tb = draw.textbbox((0, 0), label, font=font)
        tx = x0 + (THUMB - (tb[2] - tb[0])) // 2
        draw.text((tx, y0 + THUMB + 2), label, fill=(230, 230, 230), font=font)

    sheet.save(dest)
    print(f"n={n} rows={rows} cols={cols} -> {dest} ({sheet.size})")


if __name__ == "__main__":
    build_contactsheet()
