"""Generate Nobi World shots with SDXL + Nobi-LoRA, upscaled 2x with ESRGAN 4x-UltraSharp.

The upscale step is a permanent part of build_workflow() -- every shot produced by
this script is generated *and* upscaled in a single queued ComfyUI run, so no
separate post-processing pass is needed for new shots.

Usage:
    python generate_shots.py               # generate all shots in SHOTS
    python generate_shots.py s1-shot2 s1-shot3   # generate only the named shots
"""
import os
import sys

from comfy_client import run_workflow

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"

CHECKPOINT = "sd_xl_base_1.0.safetensors"
LORA = "nobi.safetensors"
UPSCALE_MODEL = "4x-UltraSharp.pth"
UPSCALE_FACTOR = 2

GEN_WIDTH = 1344
GEN_HEIGHT = 768

NOBI = (
    "nobi, 3d render, cartoon character, yellow square block head, cheerful expression, "
    "blue hoodie with white drawstrings, black pants, blue and white sneakers, brown backpack"
)
STYLE = (
    "blocky voxel 3d world, minecraft-style low-poly environment, vibrant saturated colors, "
    "children's animation, cheerful adventure game aesthetic, clean 3d render, soft global illumination"
)
BASE_NEGATIVE = (
    "photorealistic, realistic human proportions, realistic skin, text, watermark, signature, "
    "blurry, low quality, deformed, extra limbs, extra fingers, mutated, disfigured, dark, scary, "
    "grainy, jpeg artifacts, cropped, out of frame"
)
# Added after the shot2/shot3 re-generation test showed the base model drifting
# toward a generic "blue-headed voxel guy" / Minecraft Steve look without this.
ANTI_STEVE_NEGATIVE = "steve, blue head, minecraft steve"

SHOTS = [
    {
        "name": "s1-shot1",
        "lora_strength": 0.8,
        "negative_extra": "",
        "prompt": (
            f"wide establishing shot, {STYLE}, small village at the edge of a forest, "
            "wooden blocky houses, small vegetable gardens, dirt paths, warm golden morning "
            "sunlight, birds flying, tiny distant figure of nobi near a house, "
            f"{NOBI}, wide angle, cinematic composition, 16:9"
        ),
    },
    {
        "name": "s1-shot2",
        "lora_strength": 1.05,
        "negative_extra": ANTI_STEVE_NEGATIVE,
        "prompt": (
            f"extreme close-up shot on nobi's face, {STYLE}, {NOBI}, "
            "wide surprised eyes, eyebrows raised, mouth slightly open in amazement, "
            "shallow depth of field, blurred green forest background, dramatic close framing, 16:9"
        ),
    },
    {
        "name": "s1-shot3",
        "lora_strength": 1.05,
        "negative_extra": ANTI_STEVE_NEGATIVE,
        "prompt": (
            f"tracking side-view action shot, {STYLE}, {NOBI}, "
            "nobi running through a blocky forest, mid-stride dynamic running pose, motion blur on background trees, "
            "dappled sunlight through leaves, low camera angle from the side, sense of speed, 16:9"
        ),
    },
    {
        "name": "s1-shot4",
        "lora_strength": 0.8,
        "negative_extra": "",
        "prompt": (
            f"reveal shot pulling back from close-up to wide, {STYLE}, {NOBI}, "
            "nobi standing at the forest edge looking toward the distance, "
            "in the background a glowing purple magical portal hovering above a green blocky landscape, "
            "floating islands far in the sky, dramatic wide composition, magical purple glow lighting, 16:9"
        ),
    },
]


def build_workflow(prompt_text, negative_extra, filename_prefix, seed, lora_strength):
    negative = BASE_NEGATIVE + (f", {negative_extra}" if negative_extra else "")
    target_w = GEN_WIDTH * UPSCALE_FACTOR
    target_h = GEN_HEIGHT * UPSCALE_FACTOR
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CHECKPOINT}},
        "10": {
            "class_type": "LoraLoader",
            "inputs": {
                "lora_name": LORA,
                "strength_model": lora_strength,
                "strength_clip": lora_strength,
                "model": ["4", 0],
                "clip": ["4", 1],
            },
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": GEN_WIDTH, "height": GEN_HEIGHT, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_text, "clip": ["10", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["10", 1]}},
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
                "positive": ["6", 0],
                "negative": ["7", 0],
                "latent_image": ["5", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        # Permanent upscale stage -- every shot goes through this, no separate pass needed.
        "11": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_MODEL}},
        "12": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["11", 0], "image": ["8", 0]}},
        "13": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["12", 0],
                "upscale_method": "lanczos",
                "width": target_w,
                "height": target_h,
                "crop": "disabled",
            },
        },
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": filename_prefix, "images": ["13", 0]}},
    }


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    requested = set(sys.argv[1:])
    shots_to_run = [s for s in SHOTS if not requested or s["name"] in requested]

    for i, shot in enumerate(shots_to_run):
        seed = 424242 + SHOTS.index(shot)
        wf = build_workflow(shot["prompt"], shot["negative_extra"], shot["name"], seed, shot["lora_strength"])
        print(f"Queuing {shot['name']} (seed={seed}, lora_strength={shot['lora_strength']}, upscale={UPSCALE_FACTOR}x {UPSCALE_MODEL})...")
        dest = os.path.join(OUT_DIR, f"{shot['name']}.png")
        run_workflow(wf, dest)
        print(f"  saved -> {dest}")
