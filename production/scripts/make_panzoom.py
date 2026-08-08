"""Turn Scene 1 stills into Ken Burns pan/zoom clips and stitch them into a
preview video. See production/ken-burns-workflow.md section 3 (Option B).

No AI video generation involved -- movement comes purely from ffmpeg's
zoompan filter animating the camera over a still SDXL image. This is the
"Ken Burns" approach the whole project switched to after AnimateDiff proved
too unstable for character consistency.

Usage:
    python make_panzoom.py
"""
import os
import subprocess

FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
FPS = 25
W, H = 1920, 1080

SHOTS = [
    {
        "name": "s1-shot1",
        "src": "s1-shot1.png",
        "duration": 5,
        # slow zoom-in on the village, establishing shot
        "z_expr": "min(zoom+0.0012,1.15)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)*0.85",  # frame slightly above center
    },
    {
        "name": "s1-shot2",
        "src": "s1-shot2_closeup_crop.png",  # square close-up crop, not the tall full-body original
        "duration": 3,
        # punchy zoom-in on the surprised reaction
        "z_expr": "min(zoom+0.0022,1.2)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
        "pad": True,  # source isn't 16:9, pad with black bars
    },
    {
        "name": "s1-shot3",
        "src": "s1-shot3.png",
        "duration": 4,
        # pan left-to-right, matching the running direction, with a light zoom
        "z_expr": "min(zoom+0.0008,1.1)",
        "x_expr": "(iw-iw/zoom)*(on/124)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s1-shot4",
        "src": "s1-shot4.png",
        "duration": 5,
        # reveal: pull back from a tighter frame to the full wide shot
        "z_expr": "if(eq(on,0),1.18,max(zoom-0.0014,1.0))",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
]


def build_filter(shot):
    d = shot["duration"] * FPS
    pre = "scale=8000:-1,"
    if shot.get("pad"):
        pre += f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,scale=8000:-1,"
    zoompan = (
        f"zoompan=z='{shot['z_expr']}':d={d}:x='{shot['x_expr']}':y='{shot['y_expr']}'"
        f":s={W}x{H}:fps={FPS}"
    )
    return pre + zoompan + ",format=yuv420p"


def make_clip(shot):
    src = os.path.join(OUT_DIR, shot["src"])
    dest = os.path.join(OUT_DIR, f"{shot['name']}_panzoom.mp4")
    vf = build_filter(shot)
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", src,
        "-vf", vf,
        "-t", str(shot["duration"]),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        dest,
    ]
    print(f"Rendering {shot['name']} ({shot['duration']}s)...")
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


def concat_clips(clip_paths, dest):
    list_path = os.path.join(OUT_DIR, "_scene1_concat_list.txt")
    with open(list_path, "w") as f:
        for p in clip_paths:
            f.write(f"file '{p}'\n")
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", dest]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(list_path)


if __name__ == "__main__":
    clips = [make_clip(s) for s in SHOTS]
    preview = os.path.join(OUT_DIR, "episode01_scene1_preview.mp4")
    concat_clips(clips, preview)
    print(f"Preview saved -> {preview}")
