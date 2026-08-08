"""Minimal ComfyUI HTTP API client shared by the Nobi World production scripts.

Assumes a local ComfyUI install at COMFYUI_ROOT (see production/lokale-workflow.md)
with its server running on SERVER.
"""
import json
import shutil
import time
import urllib.parse
import urllib.request

SERVER = "http://127.0.0.1:8188"
COMFYUI_ROOT = r"C:\Users\Isaak\ComfyUI"
COMFYUI_INPUT_DIR = COMFYUI_ROOT + r"\input"


def queue_prompt(workflow):
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{SERVER}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def wait_for_result(prompt_id, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        with urllib.request.urlopen(f"{SERVER}/history/{prompt_id}") as resp:
            hist = json.loads(resp.read())
        if prompt_id in hist:
            outputs = hist[prompt_id].get("outputs", {})
            for node_out in outputs.values():
                if "images" in node_out:
                    return node_out["images"]
        time.sleep(2)
    raise TimeoutError(f"Timed out waiting for prompt {prompt_id}")


def fetch_image(image_info, dest_path):
    params = urllib.parse.urlencode(
        {
            "filename": image_info["filename"],
            "subfolder": image_info.get("subfolder", ""),
            "type": image_info.get("type", "output"),
        }
    )
    with urllib.request.urlopen(f"{SERVER}/view?{params}") as resp:
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(resp, f)


def run_workflow(workflow, dest_path):
    """Queue a workflow, wait for its single image output, save it to dest_path."""
    result = queue_prompt(workflow)
    prompt_id = result["prompt_id"]
    images = wait_for_result(prompt_id)
    fetch_image(images[0], dest_path)
    return prompt_id
