"""Animate the (already-approved) intro/outro still plates into real video
with LTX-Video (local, free, img2vid) instead of Ken Burns pan/zoom --
requested for these two reusable, one-time brand assets specifically.

This is NOT AnimateDiff: AnimateDiff was rejected project-wide because
text2vid generation destroyed Nobi's character consistency. LTX-Video here
runs img2vid on a still we already generated and checklist-verified with
the ControlNet pipeline, so the source pixels (and Nobi's design) are fixed
-- LTX only adds camera/particle motion on top, it doesn't redraw the
character from scratch.

Usage:
    python video_shots.py intro
    python video_shots.py outro
"""
import argparse
import json
import os
import random
import shutil
import time
import urllib.request

from comfy_client import COMFYUI_INPUT_DIR, SERVER, queue_prompt

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"

CHECKPOINT = "ltx-video-2b-v0.9.5.safetensors"
T5_MODEL = "t5xxl_fp8_e4m3fn_scaled.safetensors"
NEGATIVE = (
    "low quality, worst quality, deformed, distorted, disfigured, motion smear, motion artifacts, "
    "fused fingers, bad anatomy, weird hand, ugly, blue head, wrong character, text, watermark, logo"
)

SHOTS = {
    "intro": {
        "src": "s0-intro-nobi.png",
        "out_name": "intro_titlecard_video",
        "width": 768,
        "height": 448,
        "length": 65,
        "prompt": (
            "A cheerful cartoon character with a bright yellow square block head, wearing a vivid blue "
            "hoodie and black pants, hangs in the air with one fist raised triumphantly, its face and "
            "proportions completely unchanged and sharply in focus the entire time, "
            "surrounded by a gentle drift of blue and white toy blocks and confetti floating outward "
            "against a bright golden yellow background, soft light rays glowing outward "
            "from the character, dust and glitter particles slowly swirling through the air, the "
            "blocks slowly tumbling as they drift past the camera, an energetic joyful children's "
            "animation title sequence with vibrant saturated colors, the camera "
            "holds perfectly steady on the character, only the background elements move."
        ),
    },
    "outro": {
        "src": "s7-outro-nobi.png",
        "out_name": "outro_endscreen_video",
        "width": 768,
        "height": 448,
        "length": 145,
        "prompt": (
            "A cheerful cartoon character with a bright yellow square block head, wearing a vivid blue "
            "hoodie and black pants, stands on the edge of a floating island at golden sunset, waving one "
            "hand slowly and warmly at the camera in a friendly farewell gesture, fluffy orange and pink "
            "clouds drifting slowly across a glowing sunset sky behind the character, gentle warm light "
            "shimmering on the horizon, soft atmospheric haze drifting through the scene, a heartfelt "
            "children's animation ending scene with smooth cinematic camera motion and vibrant warm colors."
        ),
    },
}


def build_workflow(shot):
    seed = random.randint(0, 2**31 - 1)
    return {
        "38": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": T5_MODEL, "type": "ltxv", "device": "default"},
        },
        "44": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": CHECKPOINT},
        },
        "78": {
            "class_type": "LoadImage",
            "inputs": {"image": shot["_staged_filename"]},
        },
        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": shot["prompt"], "clip": ["38", 0]},
        },
        "7": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": NEGATIVE, "clip": ["38", 0]},
        },
        "77": {
            "class_type": "LTXVImgToVideo",
            "inputs": {
                "positive": ["6", 0],
                "negative": ["7", 0],
                "vae": ["44", 2],
                "image": ["78", 0],
                "width": shot["width"],
                "height": shot["height"],
                "length": shot["length"],
                "batch_size": 1,
                "strength": 0.97,
            },
        },
        "69": {
            "class_type": "LTXVConditioning",
            "inputs": {"positive": ["77", 0], "negative": ["77", 1], "frame_rate": 25},
        },
        "73": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "71": {
            "class_type": "LTXVScheduler",
            "inputs": {
                "latent": ["77", 2],
                "steps": 30,
                "max_shift": 2.05,
                "base_shift": 0.95,
                "stretch": True,
                "terminal": 0.1,
            },
        },
        "72": {
            "class_type": "SamplerCustom",
            "inputs": {
                "model": ["44", 0],
                "positive": ["69", 0],
                "negative": ["69", 1],
                "sampler": ["73", 0],
                "sigmas": ["71", 0],
                "latent_image": ["77", 2],
                "add_noise": True,
                "noise_seed": seed,
                "cfg": 3,
            },
        },
        "8": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["72", 0], "vae": ["44", 2]},
        },
        "80": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["8", 0], "fps": 24},
        },
        "81": {
            "class_type": "SaveVideo",
            "inputs": {"video": ["80", 0], "filename_prefix": shot["out_name"], "format": "auto", "codec": "auto"},
        },
    }


def wait_for_history(prompt_id, timeout=900):
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{SERVER}/history/{prompt_id}") as resp:
            hist = json.loads(resp.read())
        if prompt_id in hist:
            status = hist[prompt_id].get("status", {})
            outputs = hist[prompt_id].get("outputs", {})
            if outputs:
                return outputs
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status, indent=2))
        time.sleep(3)
    raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")


def fetch_output_file(file_info, dest_path):
    import urllib.parse
    params = urllib.parse.urlencode({
        "filename": file_info["filename"],
        "subfolder": file_info.get("subfolder", ""),
        "type": file_info.get("type", "output"),
    })
    with urllib.request.urlopen(f"{SERVER}/view?{params}") as resp:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(resp, f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("shot", choices=["intro", "outro"])
    args = parser.parse_args()

    shot = SHOTS[args.shot]
    os.makedirs(COMFYUI_INPUT_DIR, exist_ok=True)
    staged_name = f"ltxv_{args.shot}_input.png"
    shutil.copy(os.path.join(OUT_DIR, shot["src"]), os.path.join(COMFYUI_INPUT_DIR, staged_name))
    shot["_staged_filename"] = staged_name

    wf = build_workflow(shot)
    print(f"Queuing LTX-Video {args.shot} ({shot['width']}x{shot['height']}, {shot['length']} frames)...")
    result = queue_prompt(wf)
    prompt_id = result["prompt_id"]
    print(f"  prompt_id={prompt_id}, waiting...")

    outputs = wait_for_history(prompt_id)
    print("outputs keys:", {k: list(v.keys()) for k, v in outputs.items()})

    dest = os.path.join(OUT_DIR, f"{shot['out_name']}.mp4")
    found = False
    for node_out in outputs.values():
        for key in ("videos", "images", "gifs"):
            if key in node_out:
                fetch_output_file(node_out[key][0], dest)
                found = True
                break
        if found:
            break
    if not found:
        raise RuntimeError(f"No video/image output found in outputs: {outputs}")
    print(f"saved -> {dest}")
