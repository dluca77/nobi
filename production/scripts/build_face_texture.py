"""Paint Nobi's face texture (eyes, eyebrows, mouth) as a flat PNG, applied
to the front face of the 3D head cube. Matches the cheerful look established
across the approved SDXL renders: round eyes with a white highlight dot,
thin curved eyebrows, open smiling mouth.

Usage:
    python build_face_texture.py
"""
from PIL import Image, ImageDraw

OUT = r"C:\Users\Isaak\nobi\production\3d\face_texture.png"
SIZE = 1024
YELLOW = (250, 200, 20, 255)

im = Image.new("RGBA", (SIZE, SIZE), YELLOW)
d = ImageDraw.Draw(im)

# eyebrows
d.arc((260, 300, 420, 420), start=200, end=340, fill=(20, 20, 20, 255), width=22)
d.arc((600, 300, 760, 420), start=200, end=340, fill=(20, 20, 20, 255), width=22)

# eyes (white sclera, black pupil, white highlight)
for cx in (340, 680):
    cy = 480
    r = 90
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 255), outline=(20, 20, 20, 255), width=10)
    pr = 55
    d.ellipse((cx - pr, cy - pr + 10, cx + pr, cy + pr + 10), fill=(20, 20, 20, 255))
    hr = 18
    d.ellipse((cx - pr + 15, cy - pr - 5, cx - pr + 15 + hr * 2, cy - pr - 5 + hr * 2), fill=(255, 255, 255, 255))

# mouth: open smile (rounded interior with a white teeth strip along the top)
mouth_box = (330, 610, 700, 740)
d.rounded_rectangle(mouth_box, radius=60, fill=(90, 20, 15, 255), outline=(20, 20, 20, 255), width=10)
d.rounded_rectangle((355, 625, 675, 665), radius=18, fill=(255, 255, 255, 255))

im.save(OUT)
print("saved", OUT)
