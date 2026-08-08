"""Generate Nobi World Scene 2 shots (portal touch + Pixa's introduction)
with SDXL + Nobi-LoRA + Canny ControlNet.

Pixa has no LoRA and no reference photos (unlike Nobi) -- so instead of a
photo-based positioned reference, her silhouette is hand-drawn with PIL
(round body, single circular eye-lens, small antenna/thrusters) at the
exact position/scale/size she should appear. Canny edge detection on that
drawing gives ControlNet the same hard geometric constraint it gives Nobi,
so her proportions stay consistent shot-to-shot even without training data.

Usage:
    python scene2_shots.py s2-shot1 s2-shot2 s2-shot3 s2-shot4
"""
import argparse
import os
import shutil

from comfy_client import COMFYUI_INPUT_DIR, run_workflow
from PIL import Image, ImageDraw

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
REF_SOURCE_DIR = r"C:\Users\Isaak\kohya_ss\nobi_lora_dataset\img\5_nobi character"
SCRATCH_DIR = r"C:\Users\Isaak\AppData\Local\Temp\claude\C--Users-Isaak-nobi\ea0b8eca-8c87-441a-9273-162ee1154e2a\scratchpad"

CHECKPOINT = "sd_xl_base_1.0.safetensors"
LORA = "nobi.safetensors"
LORA_STRENGTH = 0.9
CONTROLNET_MODEL = "xinsir-controlnet-canny-sdxl-v2.safetensors"
CONTROLNET_STRENGTH = 0.9
CANNY_LOW = 0.4
CANNY_HIGH = 0.8

UPSCALE_MODEL = "4x-UltraSharp.pth"
UPSCALE_FACTOR = 2

NOBI = (
    "nobi, 3d render, cartoon character, (bright yellow square block head:1.25), "
    "(blue hoodie:1.2) with white drawstrings, (black pants:1.1), "
    "blue and white sneakers, brown backpack, (bright yellow hands:1.2)"
)
PIXA = (
    "pixa, small floating robot companion, round smooth white and light-blue metallic body, "
    "(single large round glowing cyan eye-lens:1.3) in the center of its body, "
    "small blue antenna on top, soft glowing particle trail underneath, no arms, no legs, "
    "cute friendly robot design, glossy plastic and brushed metal finish, gentle rim light"
)
BASE_NEGATIVE = (
    "photorealistic, realistic human proportions, tall body, long legs, adult body proportions, "
    "elongated limbs, slim body, visible neck, normal human anatomy, "
    "text, watermark, signature, "
    "blurry, low quality, deformed, extra limbs, extra fingers, mutated, disfigured, dark, scary, "
    "grainy, jpeg artifacts, cropped, out of frame"
)
NOBI_NEGATIVE = (
    "steve, minecraft steve, blue head, brown hair, human face, realistic skin, wrong character, "
    "blue hands, blue skin, white gloves, gloved hands"
)
PIXA_NEGATIVE = (
    "humanoid robot, robot with arms, robot with legs, angular robot, boxy robot, menacing robot, "
    "multiple eyes, square eye, red eye, camera lens details, wires, rust, dark metal, "
    "second character, human character"
)


def build_pixa_silhouette(canvas, cx, cy, diameter):
    draw = ImageDraw.Draw(canvas)
    r = diameter // 2
    # body
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(0, 0, 0), width=max(3, r // 15))
    # eye-lens (dominant central circle)
    er = int(r * 0.55)
    draw.ellipse((cx - er, cy - er, cx + er, cy + er), outline=(0, 0, 0), width=max(2, r // 20))
    # antenna
    draw.line((cx, cy - r, cx, cy - r - int(r * 0.35)), fill=(0, 0, 0), width=max(2, r // 25))
    ar = max(4, int(r * 0.08))
    ay = cy - r - int(r * 0.35)
    draw.ellipse((cx - ar, ay - ar, cx + ar, ay + ar), outline=(0, 0, 0), width=max(2, r // 25))
    # small thruster nubs underneath
    for dx in (-int(r * 0.4), int(r * 0.4)):
        tw = int(r * 0.18)
        draw.ellipse((cx + dx - tw, cy + r - tw // 2, cx + dx + tw, cy + r + tw), outline=(0, 0, 0), width=max(2, r // 25))


def build_positioned_reference_nobi(ref_image, width, height, char_height_frac, bottom_margin, x_frac, dest_path):
    src = Image.open(os.path.join(REF_SOURCE_DIR, ref_image)).convert("RGB")
    char_h = int(height * char_height_frac)
    scale = char_h / src.height
    char_w = int(src.width * scale)
    resized = src.resize((char_w, char_h), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    x = int((width - char_w) * x_frac)
    y = height - bottom_margin - char_h
    canvas.paste(resized, (x, y))
    canvas.save(dest_path)
    return dest_path


def build_positioned_reference_pixa(width, height, diameter_frac, x_frac, y_frac, dest_path):
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    diameter = int(height * diameter_frac)
    cx = int(width * x_frac)
    cy = int(height * y_frac)
    build_pixa_silhouette(canvas, cx, cy, diameter)
    canvas.save(dest_path)
    return dest_path


def build_positioned_reference_combo(nobi_ref_image, width, height, nobi_height_frac, nobi_x_frac,
                                      bottom_margin, pixa_diameter_frac, pixa_x_frac, pixa_y_frac, dest_path):
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    src = Image.open(os.path.join(REF_SOURCE_DIR, nobi_ref_image)).convert("RGB")
    char_h = int(height * nobi_height_frac)
    scale = char_h / src.height
    char_w = int(src.width * scale)
    resized = src.resize((char_w, char_h), Image.LANCZOS)
    x = int((width - char_w) * nobi_x_frac)
    y = height - bottom_margin - char_h
    canvas.paste(resized, (x, y))

    diameter = int(height * pixa_diameter_frac)
    cx = int(width * pixa_x_frac)
    cy = int(height * pixa_y_frac)
    build_pixa_silhouette(canvas, cx, cy, diameter)
    canvas.save(dest_path)
    return dest_path


SHOTS = [
    {
        "name": "s2-shot1",
        "width": 1344,
        "height": 768,
        "kind": "nobi",
        "ref_image": "04_Actions_pointing.png",
        "ref_char_height_frac": 0.62,
        "ref_bottom_margin": 90,
        "ref_x_frac": 0.28,
        "prompt": (
            f"medium shot, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.25), (vivid blue hoodie:1.3) with white drawstrings, "
            "(black pants:1.1), blue and white sneakers, brown backpack, (bright yellow hands:1.2), "
            "reaching one hand out toward a small glowing purple portal in front of it, "
            "hesitant curious pose, standing in a green sunlit forest clearing with brown tree trunks, "
            "character lit with neutral daylight unaffected by the portal's glow, "
            "blocky voxel 3d world, vibrant saturated colors"
        ),
        "extra_negative": (
            f"{NOBI_NEGATIVE}, purple hoodie, magenta hoodie, pink hoodie, purple sleeve, violet hoodie, "
            "fire, flames, wildfire, forest fire, burning trees, embers, smoke, orange sky, sunset"
        ),
    },
    {
        "name": "s2-shot2",
        "width": 768,
        "height": 1344,
        "kind": "nobi",
        "ref_image": "03_Emotions_wow.png",
        "ref_char_height_frac": 0.8,
        "ref_bottom_margin": 250,
        "ref_x_frac": 0.5,
        "prompt": (
            f"close-up shot, {NOBI}, "
            "startled shocked expression, eyes wide open, leaning back in surprise, "
            "dappled forest light on its face, blurred forest background, empty hands at its sides, "
            "blocky voxel 3d world, vibrant saturated colors"
        ),
        "extra_negative": f"{NOBI_NEGATIVE}, goggles, glasses, eye rings, ski mask, controller, gamepad, "
                           "device in hand, holding object, holding controller, mechanical hands, robotic gloves",
    },
    {
        "name": "s2-shot3",
        "width": 1344,
        "height": 768,
        "kind": "pixa",
        "pixa_diameter_frac": 0.42,
        "pixa_x_frac": 0.5,
        "pixa_y_frac": 0.45,
        "prompt": (
            f"{PIXA}, "
            "(spawning in a burst of bright light particles and sparkles:1.2), floating in mid-air, "
            "glowing purple portal blurred in the background, magical light flashes, "
            "blocky voxel 3d world, vibrant saturated colors, dramatic reveal lighting"
        ),
        "extra_negative": PIXA_NEGATIVE,
    },
    {
        # Nobi-only plate for shot4 -- Pixa is composited in afterward from
        # her shot3 cutout instead of sharing one diffusion pass with her,
        # since 3 attempts at generating them together all cross-bled
        # (Nobi picking up blue/glowing-ring qualities from Pixa's prompt).
        "name": "s2-shot4-nobi",
        "width": 1344,
        "height": 768,
        "kind": "nobi",
        "ref_image": "04_Actions_looking_up.png",
        "ref_char_height_frac": 0.62,
        "ref_bottom_margin": 90,
        "ref_x_frac": 0.22,
        "prompt": (
            f"wide shot, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.25), (vivid blue hoodie:1.3) with white drawstrings, "
            "(black pants:1.1), blue and white sneakers, brown backpack, (bright yellow hands:1.2), "
            "looking up and to the right in amazement, mouth open in wonder, "
            "(hood down around the shoulders, bare head fully exposed, no hood on head:1.35), "
            "standing in a green sunlit forest clearing with brown tree trunks, "
            "character lit with neutral daylight, "
            "blocky voxel 3d world, vibrant saturated colors"
        ),
        "extra_negative": (
            f"{NOBI_NEGATIVE}, "
            "fire, flames, wildfire, forest fire, burning trees, embers, smoke, orange sky, sunset, "
            "blue tinted image, blue color grade, monochrome blue, purple gloves, purple hands, "
            "hood up, hood covering head, hooded"
        ),
    },
    {
        "name": "s2-shot4",
        "width": 1344,
        "height": 768,
        "kind": "combo",
        "nobi_ref_image": "01_Turnarounds_three_quarter_front_left.png",
        "nobi_height_frac": 0.62,
        "nobi_x_frac": 0.22,
        "nobi_bottom_margin": 90,
        "pixa_diameter_frac": 0.22,
        "pixa_x_frac": 0.62,
        "pixa_y_frac": 0.38,
        "prompt": (
            f"wide two-shot, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.3), (vivid blue hoodie:1.2) with white drawstrings, "
            "(black pants:1.1), blue and white sneakers, brown backpack, (bright yellow hands:1.2), "
            "looking up in amazement, standing in a green sunlit forest clearing with brown tree trunks and grass, "
            "warm neutral daylight on nobi, "
            "small round white and light-blue robot companion floating at head height to the right, "
            "(flat glowing circular eye-lens screen, no iris, no pupil, no eyelashes:1.3), small antenna on top, "
            "a small purple portal glimpsed far in the background between the trees, "
            "blocky voxel 3d world, vibrant saturated colors, no color tint over the whole image"
        ),
        "extra_negative": (
            f"{NOBI_NEGATIVE}, {PIXA_NEGATIVE}, "
            "blue tinted image, blue color grade, monochrome blue, blue background, blue studio background, "
            "realistic eyeball, iris, pupil, eyelashes, sclera, "
            "blue head, cyan head, teal head, blue face, blue-tinted head, "
            "gear shaped, sun shaped, radiating spikes, cog, star shaped"
        ),
    },
]


def build_workflow(prompt_text, filename_prefix, seed, ref_filename, width, height, extra_negative=""):
    target_w = width * UPSCALE_FACTOR
    target_h = height * UPSCALE_FACTOR
    negative = f"{BASE_NEGATIVE}"
    if extra_negative:
        negative = f"{negative}, {extra_negative}"
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "10": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": LORA,
                "strength_model": LORA_STRENGTH,
                "strength_clip": LORA_STRENGTH,
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        },
        "40": {"class_type": "LoadImage", "inputs": {"image": ref_filename}},
        "41": {"class_type": "Canny", "inputs": {"image": ["40", 0], "low_threshold": CANNY_LOW, "high_threshold": CANNY_HIGH}},
        "42": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": CONTROLNET_MODEL}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_text, "clip": ["10", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["10", 1]}},
        "43": {
            "class_type": "ControlNetApplyAdvanced",
            "inputs": {
                "positive": ["6", 0],
                "negative": ["7", 0],
                "control_net": ["42", 0],
                "image": ["41", 0],
                "strength": CONTROLNET_STRENGTH,
                "start_percent": 0.0,
                "end_percent": 1.0,
            },
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 32,
                "cfg": 7.0,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["10", 0],
                "positive": ["43", 0],
                "negative": ["43", 1],
                "latent_image": ["5", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "11": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_MODEL}},
        "12": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["11", 0], "image": ["8", 0]}},
        "13": {
            "class_type": "ImageScale",
            "inputs": {"image": ["12", 0], "upscale_method": "lanczos", "width": target_w, "height": target_h, "crop": "disabled"},
        },
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["13", 0]}},
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shots", nargs="*")
    parser.add_argument("--controlnet-strength", type=float, default=CONTROLNET_STRENGTH)
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(COMFYUI_INPUT_DIR, exist_ok=True)
    requested = set(args.shots)
    shots_to_run = [s for s in SHOTS if not requested or s["name"] in requested]

    for shot in shots_to_run:
        seed = 600000 + SHOTS.index(shot) + args.seed_offset
        width, height = shot["width"], shot["height"]

        local_ref = os.path.join(SCRATCH_DIR, f"{shot['name']}_positioned_ref.png")
        if shot["kind"] == "nobi":
            build_positioned_reference_nobi(
                shot["ref_image"], width, height,
                shot["ref_char_height_frac"], shot["ref_bottom_margin"], shot["ref_x_frac"],
                local_ref,
            )
        elif shot["kind"] == "pixa":
            build_positioned_reference_pixa(
                width, height, shot["pixa_diameter_frac"], shot["pixa_x_frac"], shot["pixa_y_frac"],
                local_ref,
            )
        else:  # combo
            build_positioned_reference_combo(
                shot["nobi_ref_image"], width, height, shot["nobi_height_frac"], shot["nobi_x_frac"],
                shot["nobi_bottom_margin"], shot["pixa_diameter_frac"], shot["pixa_x_frac"], shot["pixa_y_frac"],
                local_ref,
            )

        ref_filename = f"pixa_ref_{shot['name']}_positioned.png"
        shutil.copy(local_ref, os.path.join(COMFYUI_INPUT_DIR, ref_filename))

        wf = build_workflow(shot["prompt"], shot["name"], seed, ref_filename, width, height, shot.get("extra_negative", ""))
        wf["43"]["inputs"]["strength"] = args.controlnet_strength

        print(f"Queuing {shot['name']} (seed={seed}, kind={shot['kind']}, canvas={width}x{height})...")
        dest = os.path.join(OUT_DIR, f"{shot['name']}.png")
        run_workflow(wf, dest)
        print(f"  saved -> {dest}")
