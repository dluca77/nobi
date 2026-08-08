"""Generate Nobi World shots with SDXL + Nobi-LoRA + IPAdapter reference-locking,
upscaled 2x with ESRGAN 4x-UltraSharp.

Every shot that contains Nobi goes through the SAME mandatory pipeline, no
exceptions, because bare LoRA conditioning was not reliably keeping the
character on-model (blue heads, human hair, wrong outfit):

  1. LoraLoader: nobi.safetensors @ strength_model=1.0, strength_clip=1.0
  2. IPAdapterAdvanced: reference images (front + 3/4-view turnaround, batched
     and averaged) locking in the actual character appearance, weight
     configurable per call (default 0.75, escalate to 0.9-1.0 on a failed
     visual check instead of shipping a bad frame)
  3. Full, un-shortened Nobi tag in the positive prompt
  4. Negative prompt always includes MANDATORY_NEGATIVE (steve/blue
     head/human face etc.), on top of the general BASE_NEGATIVE
  5. UpscaleModelLoader + ImageUpscaleWithModel (4x-UltraSharp) + ImageScale
     down to exactly 2x generation resolution (>=2688x1536 at 1344x768 base)

Usage:
    python generate_shots.py                                # all shots in SHOTS
    python generate_shots.py s1-shot2 s1-shot3               # only these
    python generate_shots.py s1-shot2 --ipadapter-weight 0.9  # retry at higher weight
"""
import argparse
import os
import shutil

from comfy_client import COMFYUI_INPUT_DIR, run_workflow

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
# IMPORTANT: reference images MUST come from the actual Kohya training set,
# not the repo's images/ copies -- those repo copies are taller (e.g. 144x284
# vs 140x249 for front.png) because they still have the baked-in "FRONT" /
# "CLOSE UP FACE" caption band burned into the png. Feeding that captioned
# version into IPAdapter as a single reference is what caused the model to
# hallucinate garbled caption text ("LOUE-FADCE-") into a generated shot.
REF_SOURCE_DIR = r"C:\Users\Isaak\kohya_ss\nobi_lora_dataset\img\5_nobi character"

CHECKPOINT = "sd_xl_base_1.0.safetensors"
LORA = "nobi.safetensors"
LORA_STRENGTH = 1.0
CLIP_VISION_MODEL = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
IPADAPTER_MODEL = "ip-adapter-plus_sdxl_vit-h.safetensors"
IPADAPTER_WEIGHT_DEFAULT = 0.75
# Full-body turnaround references, batched + averaged by IPAdapter -- good for
# wide/action shots. IMPORTANT: feeding these into a close-up shot pulls the
# *composition* toward a full-body figure too, which cropped the head clean
# off in testing. Close-up shots must use CLOSEUP_REFS instead.
FULL_BODY_REFS = ["01_Turnarounds_front.png", "01_Turnarounds_three_quarter_front_left.png"]
CLOSEUP_REFS = ["02_Views_Closeups_closeup_face.png"]
# Turnaround refs mostly show hands hanging at the side (small, low-signal for
# CLIP vision); these two show a large, prominent, clearly-yellow hand instead.
HAND_REFS = ["04_Actions_thumbs_up.png", "04_Actions_pointing.png"]

UPSCALE_MODEL = "4x-UltraSharp.pth"
UPSCALE_FACTOR = 2

GEN_WIDTH = 1344
GEN_HEIGHT = 768
CFG_DEFAULT = 8.0

NOBI = (
    "nobi, chibi toy figure proportions, huge oversized square head roughly 40% of total body height, "
    "tiny short compact body, short stubby legs, small simple arms, no visible neck, head resting directly "
    "on the shoulders, vinyl toy figurine render, simple flat toy lighting, "
    "3d render, cartoon character, yellow square block head, cheerful expression, "
    "blue hoodie with white drawstrings, black pants, blue and white sneakers, brown backpack"
)
STYLE = (
    "blocky voxel 3d world, minecraft-style low-poly environment, vibrant saturated colors, "
    "children's animation, cheerful adventure game aesthetic, clean 3d render, soft global illumination"
)
BASE_NEGATIVE = (
    "photorealistic, realistic human proportions, tall body, long legs, adult body proportions, "
    "elongated limbs, slim body, visible neck, normal human anatomy, video game protagonist, "
    "text, watermark, signature, "
    "blurry, low quality, deformed, extra limbs, extra fingers, mutated, disfigured, dark, scary, "
    "grainy, jpeg artifacts, cropped, out of frame, cropped head, head cut off, "
    "top of head missing, head out of frame"
)
# Mandatory for every Nobi shot -- LoRA alone kept drifting toward Minecraft
# Steve / a human-haired hooded kid instead of Nobi's plain yellow block head.
# NOTE: every attempt to ALSO fix the hand color / eye smudge via prompt
# additions (weighted terms, more negatives, higher CFG) made this baseline
# less stable, not more -- see generate_shots.py history / commit log. This is
# the exact config that reliably produces a correct head/hoodie/backpack/
# pants/shoes; the remaining hand-color defect is fixed locally in
# post-processing instead (see upscale_existing.py), not by re-rolling this.
MANDATORY_NEGATIVE = "steve, minecraft steve, blue head, brown hair, human face, realistic skin, wrong character"

SHOTS = [
    {
        "name": "s1-shot1",
        "prompt": (
            f"wide establishing shot, {STYLE}, small village at the edge of a forest, "
            "wooden blocky houses, small vegetable gardens, dirt paths, warm golden morning "
            "sunlight, birds flying, tiny distant figure of nobi near a house, "
            f"{NOBI}, wide angle, cinematic composition, 16:9"
        ),
    },
    {
        "name": "s1-shot2",
        # Tall canvas + full-body refs (the known-good combo for correct
        # color): let IPAdapter's full-body compositional pull play out with
        # room to breathe instead of fighting it, then crop to a close-up in
        # post via upscale_existing.py's --crop. Single close-up references
        # and prompt-only framing fixes both failed badly in testing (see
        # generate_shots.py module docstring / commit history for the log).
        "width": 768,
        "height": 1344,
        # HAND_REFS (thumbs_up/pointing) caused a full pose-sheet collage
        # collapse in 3/3 variants -- those source images are themselves small
        # "sprite sheet" crops with lots of white space, same failure class as
        # the earlier closeup_face.png disaster. Full-body turnarounds are the
        # only references that have reliably produced ONE coherent figure.
        "ref_images": FULL_BODY_REFS,
        "prompt": (
            f"full body standing shot, {STYLE}, {NOBI}, "
            "surprised expression, wide eyes, eyebrows raised, mouth slightly open in amazement, "
            "standing facing camera, dense green forest background, natural daylight"
        ),
    },
    {
        "name": "s1-shot3",
        "prompt": (
            f"tracking side-view action shot, {STYLE}, {NOBI}, "
            "nobi running through a blocky forest, mid-stride dynamic running pose, motion blur on background trees, "
            "dappled sunlight through leaves, low camera angle from the side, sense of speed, 16:9"
        ),
    },
    {
        "name": "s1-shot4",
        "prompt": (
            f"reveal shot pulling back from close-up to wide, {STYLE}, {NOBI}, "
            "nobi standing at the forest edge looking toward the distance, "
            "in the background a glowing purple magical portal hovering above a green blocky landscape, "
            "floating islands far in the sky, dramatic wide composition, magical purple glow lighting, 16:9"
        ),
    },
]


def ensure_ref_images_staged(ref_images):
    os.makedirs(COMFYUI_INPUT_DIR, exist_ok=True)
    staged = []
    for fname in ref_images:
        dest = os.path.join(COMFYUI_INPUT_DIR, f"nobi_ref_{fname}")
        shutil.copy(os.path.join(REF_SOURCE_DIR, fname), dest)
        staged.append(os.path.basename(dest))
    return staged


def build_workflow(prompt_text, filename_prefix, seed, ipadapter_weight, ref_filenames, width=GEN_WIDTH, height=GEN_HEIGHT, weight_type="linear", start_at=0.0, cfg=CFG_DEFAULT):
    negative = f"{BASE_NEGATIVE}, {MANDATORY_NEGATIVE}"
    target_w = width * UPSCALE_FACTOR
    target_h = height * UPSCALE_FACTOR

    nodes = {}
    if len(ref_filenames) == 1:
        nodes["30"] = {"class_type": "LoadImage", "inputs": {"image": ref_filenames[0]}}
        ipadapter_image_ref = ["30", 0]
    else:
        ref1, ref2 = ref_filenames
        nodes["30"] = {"class_type": "LoadImage", "inputs": {"image": ref1}}
        nodes["31"] = {"class_type": "LoadImage", "inputs": {"image": ref2}}
        nodes["32"] = {"class_type": "ImageBatch", "inputs": {"image1": ["30", 0], "image2": ["31", 0]}}
        ipadapter_image_ref = ["32", 0]

    nodes.update({
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
        # -- IPAdapter reference locking (LoadImage/ImageBatch nodes for refs
        # are already in `nodes` from the block above) --
        "33": {"class_type": "CLIPVisionLoader", "inputs": {"clip_name": CLIP_VISION_MODEL}},
        "34": {"class_type": "IPAdapterModelLoader", "inputs": {"ipadapter_file": IPADAPTER_MODEL}},
        "35": {
            "class_type": "IPAdapterAdvanced",
            "inputs": {
                "model": ["10", 0],
                "ipadapter": ["34", 0],
                "image": ipadapter_image_ref,
                "weight": ipadapter_weight,
                "weight_type": weight_type,
                "combine_embeds": "average",
                "start_at": start_at,
                "end_at": 1.0,
                "embeds_scaling": "V only",
                "clip_vision": ["33", 0],
            },
        },
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt_text, "clip": ["10", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["10", 1]}},
        "3": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 32,
                "cfg": cfg,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": 1.0,
                "model": ["35", 0],
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
    })
    return nodes


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shots", nargs="*", help="shot names to generate, default = all")
    parser.add_argument("--ipadapter-weight", type=float, default=IPADAPTER_WEIGHT_DEFAULT)
    parser.add_argument("--weight-type", default="linear")
    parser.add_argument("--start-at", type=float, default=0.0, help="delay IPAdapter influence until this fraction of denoising")
    parser.add_argument("--seed-offset", type=int, default=0, help="add to the base seed, useful for retries")
    parser.add_argument("--cfg", type=float, default=CFG_DEFAULT)
    parser.add_argument("--variants", type=int, default=1, help="generate N seed variants per shot, e.g. for a side-by-side pick")
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    requested = set(args.shots)
    shots_to_run = [s for s in SHOTS if not requested or s["name"] in requested]

    for shot in shots_to_run:
        width = shot.get("width", GEN_WIDTH)
        height = shot.get("height", GEN_HEIGHT)
        ref_images = shot.get("ref_images", FULL_BODY_REFS)
        ref_filenames = ensure_ref_images_staged(ref_images)
        for v in range(args.variants):
            seed = 424242 + SHOTS.index(shot) + args.seed_offset + v * 1000
            variant_suffix = f"_v{v + 1}" if args.variants > 1 else ""
            filename_prefix = f"{shot['name']}{variant_suffix}"
            wf = build_workflow(shot["prompt"], filename_prefix, seed, args.ipadapter_weight, ref_filenames, width, height, args.weight_type, args.start_at, args.cfg)
            print(
                f"Queuing {filename_prefix} (seed={seed}, lora={LORA_STRENGTH}, cfg={args.cfg}, "
                f"ipadapter_weight={args.ipadapter_weight}, refs={ref_images}, canvas={width}x{height}, "
                f"upscale={UPSCALE_FACTOR}x {UPSCALE_MODEL})..."
            )
            dest = os.path.join(OUT_DIR, f"{filename_prefix}.png")
            run_workflow(wf, dest)
            print(f"  saved -> {dest}")
