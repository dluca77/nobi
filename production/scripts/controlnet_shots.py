"""Generate Nobi World shots with SDXL + Nobi-LoRA + Canny ControlNet.

Why this exists: the LoRA+IPAdapter pipeline (generate_shots.py) reliably
transferred Nobi's COLORS (yellow head, blue hoodie) but never his chibi
BODY PROPORTIONS (huge head ~40% of height, short stubby body/legs, no
visible neck) -- neither the LoRA nor IPAdapter provide a hard geometric
constraint, so the SDXL base model's adult-human proportion prior kept
winning. A Canny edge map extracted from the actual reference sheet, fed
through ControlNet, forces the diffusion process to follow that exact
silhouette -- so proportions are no longer up to the prompt.

Pipeline:
  1. A "positioned reference" image: the clean turnaround character (from
     the Kohya training set) scaled up and placed on a blank canvas at the
     exact position/scale it should appear in the final shot.
  2. Canny edge detection on that positioned reference.
  3. ControlNetApplyAdvanced (xinsir SDXL Canny v2) at high strength --
     this is what enforces the proportions, not the prompt.
  4. LoraLoader (nobi.safetensors) still supplies color/texture fidelity.
  5. Same upscale stage as generate_shots.py (4x-UltraSharp -> 2x).

Usage:
    python controlnet_shots.py s1-shot2
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
    "nobi, 3d render, cartoon character, (bright yellow square block head:1.25), cheerful expression, "
    "(blue hoodie:1.15) with white drawstrings, (black pants:1.1), "
    "blue and white sneakers, brown backpack, (bright yellow hands:1.15)"
)
BASE_NEGATIVE = (
    "photorealistic, realistic human proportions, tall body, long legs, adult body proportions, "
    "elongated limbs, slim body, visible neck, normal human anatomy, video game protagonist, "
    "text, watermark, signature, "
    "blurry, low quality, deformed, extra limbs, extra fingers, mutated, disfigured, dark, scary, "
    "grainy, jpeg artifacts, cropped, out of frame"
)
# Canny gives geometry only, no color info -- background colors keep bleeding
# into clothing/skin: "green forest" -> green hoodie+pants, then overcorrecting
# the blue weight -> white/pale head and a blue color cast over the whole
# scene. Keep per-part color weights moderate (~1.1-1.25), not 1.3+.
MANDATORY_NEGATIVE = (
    "steve, minecraft steve, blue head, brown hair, human face, realistic skin, wrong character, "
    "blue hands, blue skin, green hoodie, green pants, green clothing, olive clothing, khaki clothing, "
    "white head, pale head, colorless head, gray head, desaturated head, blue color cast, monochrome"
)

SHOTS = [
    {
        "name": "s1-shot2",
        "width": 768,
        "height": 1344,
        "ref_image": "01_Turnarounds_front.png",
        "ref_char_height_frac": 0.85,  # how much of canvas height the character fills
        "ref_bottom_margin": 60,
        "ref_x_frac": 0.5,
        "prompt": (
            f"full body standing shot, {NOBI}, "
            "surprised expression, wide eyes, eyebrows raised, mouth slightly open in amazement, "
            "standing facing camera, blurred forest trees in the background, natural daylight, "
            "blocky voxel 3d world, vibrant saturated colors, clothing colors unaffected by background"
        ),
    },
    {
        # Script: "Shot 3: Tracking shot Nobi rennend door bos, camera van opzij."
        # v1 result: autumn-gold forest bled into the hoodie (turned yellow
        # instead of blue) and the base model defaulted to white gloves
        # instead of bare yellow hands. Fixed by: anchoring the forest to
        # green (not "dappled sunlight" alone, which reads as golden-hour),
        # raising the hoodie/hand weights, and negating gloves + autumn tones.
        "name": "s1-shot3",
        "width": 1344,
        "height": 768,
        "ref_image": "04_Actions_running.png",
        "ref_char_height_frac": 0.62,
        "ref_bottom_margin": 90,
        "ref_x_frac": 0.32,  # rule-of-thirds, running toward the right = deeper into the shot
        "prompt": (
            f"tracking side-view action shot, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.25), cheerful expression, "
            "(vivid blue hoodie:1.3) with white drawstrings, (black pants:1.1), "
            "blue and white sneakers, brown backpack, (bare bright yellow hands, no gloves:1.3), "
            "mid-stride dynamic running pose, running through a green sunlit forest, dappled light through green leaves, "
            "motion blur on background trees, low camera angle from the side, sense of speed, "
            "blocky voxel 3d world, vibrant saturated colors, clothing colors unaffected by background"
        ),
        "extra_negative": (
            "yellow hoodie, gold hoodie, orange hoodie, tan hoodie, brown hoodie, "
            "white gloves, gloved hands, mittens, autumn leaves, orange forest, golden forest, yellow forest"
        ),
    },
    {
        # Script: "Shot 4: Reveal shot portaal — camera trekt terug van close-up naar wide."
        # v1 result: the purple/pink portal environment bled into the
        # backpack (turned purple instead of brown) and hoodie/sneakers lost
        # their blue. Fixed by: softening the blanket "purple glow lighting"
        # to a localized portal glow, raising backpack/hoodie/sneaker
        # weights, and negating purple/pink clothing explicitly.
        "name": "s1-shot4",
        "width": 1344,
        "height": 768,
        "ref_image": "01_Turnarounds_back.png",
        "ref_char_height_frac": 0.4,
        "ref_bottom_margin": 70,
        "ref_x_frac": 0.28,  # small, off-center figure so the portal reveal on the right reads clearly
        "prompt": (
            f"reveal shot, wide dramatic composition, nobi, 3d render, cartoon character, "
            "(bright yellow square block head:1.25), "
            "(vivid blue hoodie:1.3) with white drawstrings, (black pants:1.1), "
            "(blue and white sneakers:1.2), (solid brown leather backpack:1.3), (bright yellow hands:1.2), "
            "seen from behind, standing at the forest edge looking toward the distance, "
            "character lit with neutral daylight unaffected by the portal's glow, "
            "in the background a glowing purple magical portal hovering above a rocky blocky landscape, "
            "floating islands far in the sky, "
            "blocky voxel 3d world, vibrant saturated colors"
        ),
        "extra_negative": (
            "purple hoodie, pink hoodie, magenta hoodie, violet hoodie, "
            "purple backpack, pink backpack, magenta backpack, violet backpack, "
            "purple pants, purple sneakers, pink sneakers, gray sneakers, "
            "clothing tinted purple, clothing tinted pink, purple color cast on character"
        ),
    },
]
# NOTE: three prompt-only attempts at shot4 all failed to get BOTH the
# character colors AND the portal/sky color right at once -- protecting the
# character from the purple environment desaturates the portal (v2, portal
# went green/gold), and strengthening the portal bleeds purple/red onto the
# ENTIRE character (v3, total color collapse). This v2-equivalent prompt is
# used as the base specifically because it gets the character right; the
# portal/sky color is fixed afterward with a local, masked hue-correction
# pass (see fix_shot4_portal.py in the scratchpad) instead of more re-rolling.


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
    negative = f"{BASE_NEGATIVE}, {MANDATORY_NEGATIVE}"
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
        seed = 500000 + SHOTS.index(shot) + args.seed_offset
        width, height = shot["width"], shot["height"]

        local_ref = os.path.join(SCRATCH_DIR, f"{shot['name']}_positioned_ref.png")
        build_positioned_reference(
            shot["ref_image"], width, height,
            shot["ref_char_height_frac"], shot["ref_bottom_margin"], shot["ref_x_frac"],
            local_ref,
        )
        ref_filename = f"nobi_ref_{shot['name']}_positioned.png"
        shutil.copy(local_ref, os.path.join(COMFYUI_INPUT_DIR, ref_filename))

        CONTROLNET_STRENGTH_RUN = args.controlnet_strength
        wf = build_workflow(shot["prompt"], shot["name"], seed, ref_filename, width, height, shot.get("extra_negative", ""))
        wf["43"]["inputs"]["strength"] = CONTROLNET_STRENGTH_RUN

        print(f"Queuing {shot['name']} (seed={seed}, controlnet_strength={CONTROLNET_STRENGTH_RUN}, canvas={width}x{height})...")
        dest = os.path.join(OUT_DIR, f"{shot['name']}.png")
        run_workflow(wf, dest)
        print(f"  saved -> {dest}")
