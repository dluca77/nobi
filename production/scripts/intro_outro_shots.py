"""Generate the character plates for the intro title card and outro end
screen (see script.md TITELCARD and SCENE 7 directions), same SDXL +
Nobi-LoRA + Canny ControlNet pipeline as every other shot. Text/graphics
(logo, subscribe button, thumbnail box) are NOT generated here -- SDXL
renders text badly, so those are composited afterward in
build_intro_outro.py using clean typography.

Usage:
    python intro_outro_shots.py intro outro
"""
import argparse
import os
import shutil

from comfy_client import COMFYUI_INPUT_DIR, run_workflow
from PIL import Image

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
    "(vivid blue hoodie:1.3) with white drawstrings, (black pants:1.1), "
    "blue and white sneakers, brown backpack, (bright yellow hands:1.2)"
)
BASE_NEGATIVE = (
    "photorealistic, realistic human proportions, tall body, long legs, adult body proportions, "
    "elongated limbs, slim body, visible neck, normal human anatomy, "
    "blurry, low quality, deformed, extra limbs, extra fingers, mutated, disfigured, dark, scary, "
    "grainy, jpeg artifacts, cropped, out of frame, "
    "text, watermark, signature, logo, letters, words, writing"
)
NOBI_NEGATIVE = (
    "steve, minecraft steve, blue head, brown hair, human face, realistic skin, wrong character, "
    "blue hands, blue skin, white gloves, gloved hands"
)

SHOTS = [
    {
        "name": "s0-intro-nobi",
        "width": 1344,
        "height": 768,
        "ref_image": "04_Actions_jumping.png",
        "ref_char_height_frac": 0.68,
        "ref_bottom_margin": 60,
        "ref_x_frac": 0.5,
        "prompt": (
            f"dynamic action shot, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.4), "
            "(vivid blue hoodie:1.3) with white drawstrings, (black pants:1.1), "
            "blue and white sneakers, brown backpack, (bright yellow hands:1.2), "
            "jumping mid-air with one fist raised, energetic excited expression, "
            "colorful blue and white blocky cubes bursting and flying outward around it, "
            "dust cloud particle burst, confetti-like blocks, motion lines, "
            "blocky voxel 3d world, dramatic dynamic lighting, vibrant saturated colors, "
            "exciting reveal moment, empty space around the character for a title overlay"
        ),
        "extra_negative": f"{NOBI_NEGATIVE}, blue face, cyan head, teal head, blue-tinted head",
    },
    {
        "name": "s7-outro-nobi",
        "width": 1344,
        "height": 768,
        "ref_image": "02_Views_Closeups_full_body_wave.png",
        "ref_char_height_frac": 0.62,
        "ref_bottom_margin": 90,
        "ref_x_frac": 0.28,
        "prompt": (
            f"full body shot, {NOBI}, "
            "waving one hand cheerfully at the camera, warm friendly smile, "
            "standing on the edge of a floating island at golden sunset, "
            "floating islands and soft clouds in the background, "
            "blocky voxel 3d world, warm golden lighting, vibrant saturated colors, "
            "friendly farewell mood, empty space on the right for graphics overlay"
        ),
        "extra_negative": NOBI_NEGATIVE,
    },
]


def build_positioned_reference(ref_image, width, height, char_height_frac, bottom_margin, x_frac, dest_path):
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


NAME_MAP = {"intro": "s0-intro-nobi", "outro": "s7-outro-nobi"}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shots", nargs="*")
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(COMFYUI_INPUT_DIR, exist_ok=True)
    requested = {NAME_MAP.get(s, s) for s in args.shots}
    shots_to_run = [s for s in SHOTS if not requested or s["name"] in requested]

    for shot in shots_to_run:
        seed = 700000 + SHOTS.index(shot) + args.seed_offset
        width, height = shot["width"], shot["height"]

        local_ref = os.path.join(SCRATCH_DIR, f"{shot['name']}_positioned_ref.png")
        build_positioned_reference(
            shot["ref_image"], width, height,
            shot["ref_char_height_frac"], shot["ref_bottom_margin"], shot["ref_x_frac"],
            local_ref,
        )
        ref_filename = f"io_ref_{shot['name']}_positioned.png"
        shutil.copy(local_ref, os.path.join(COMFYUI_INPUT_DIR, ref_filename))

        wf = build_workflow(shot["prompt"], shot["name"], seed, ref_filename, width, height, shot.get("extra_negative", ""))

        print(f"Queuing {shot['name']} (seed={seed}, canvas={width}x{height})...")
        dest = os.path.join(OUT_DIR, f"{shot['name']}.png")
        run_workflow(wf, dest)
        print(f"  saved -> {dest}")
