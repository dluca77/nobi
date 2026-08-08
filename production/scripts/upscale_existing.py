"""Pure post-processing upscale of already-generated shot PNGs -- no re-generation.

Copies each source PNG into the local ComfyUI input folder, runs it through
UpscaleModelLoader + ImageUpscaleWithModel (ESRGAN 4x-UltraSharp) followed by an
ImageScale down-sample to the exact target factor, and writes the result back.

Usage:
    python upscale_existing.py s1-shot1.png s1-shot4.png     # 2x, overwrite in place
    python upscale_existing.py --factor 2 --suffix _2x s1-shot1.png
"""
import argparse
import os
import shutil
import tempfile

from PIL import Image

from comfy_client import COMFYUI_INPUT_DIR, run_workflow

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
UPSCALE_MODEL = "4x-UltraSharp.pth"


def build_workflow(input_filename, target_w, target_h):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": input_filename}},
        "11": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": UPSCALE_MODEL}},
        "12": {"class_type": "ImageUpscaleWithModel", "inputs": {"upscale_model": ["11", 0], "image": ["1", 0]}},
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
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "upscale_" + os.path.splitext(input_filename)[0], "images": ["13", 0]}},
    }


def upscale_file(src_path, factor=2, suffix=None):
    with Image.open(src_path) as im:
        orig_w, orig_h = im.size
    target_w, target_h = orig_w * factor, orig_h * factor

    input_filename = os.path.basename(src_path)
    os.makedirs(COMFYUI_INPUT_DIR, exist_ok=True)
    shutil.copy(src_path, os.path.join(COMFYUI_INPUT_DIR, input_filename))

    wf = build_workflow(input_filename, target_w, target_h)
    print(f"Upscaling {src_path} ({orig_w}x{orig_h} -> {target_w}x{target_h}, {UPSCALE_MODEL})...")

    fd, tmp_path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    run_workflow(wf, tmp_path)

    if suffix:
        base, ext = os.path.splitext(src_path)
        dest_path = f"{base}{suffix}{ext}"
    else:
        dest_path = src_path  # overwrite in place, atomically

    os.replace(tmp_path, dest_path)
    print(f"  saved -> {dest_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="PNG filenames (relative to production/output) or absolute paths")
    parser.add_argument("--factor", type=int, default=2)
    parser.add_argument("--suffix", default=None, help="If set, write to <name><suffix>.png instead of overwriting")
    args = parser.parse_args()

    for f in args.files:
        src = f if os.path.isabs(f) else os.path.join(OUT_DIR, f)
        upscale_file(src, factor=args.factor, suffix=args.suffix)
