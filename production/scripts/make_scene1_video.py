"""Build a properly synced Scene 1 preview: per-shot Dutch voice-over
segments (Piper TTS) drive each shot's pan/zoom duration, instead of a
fixed clip length + freeze-frame padding.

Usage:
    python make_scene1_video.py
"""
import os
import subprocess
import wave

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
VOICE_MODEL = r"C:\Users\Isaak\nobi\production\voices\nl_NL-mls-medium.onnx"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
FFPROBE = FFMPEG.replace("ffmpeg.exe", "ffprobe.exe")
PIPER_PY = r"C:\Users\Isaak\ComfyUI\venv\Scripts\python.exe"
FPS = 25
W, H = 1920, 1080
PAD_SECONDS = 0.6  # breathing room after each line before the next shot cuts in

SHOTS = [
    {
        "name": "s1-shot1",
        "src": "s1-shot1.png",
        "vo": "Het begon allemaal vanmorgen. Ik was gewoon mijn wortels aan het oogsten... heel normaal ochtendje...",
        "z_expr": "min(zoom+0.0012,1.15)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)*0.85",
    },
    {
        "name": "s1-shot2",
        "src": "s1-shot2_closeup_crop.png",
        "vo": "Toen ik dit hoorde.",
        "z_expr": "min(zoom+0.0022,1.2)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
        "pad": True,
    },
    {
        "name": "s1-shot3",
        "src": "s1-shot3.png",
        "vo": "Ik liep het bos in, en toen zag ik het.",
        "z_expr": "min(zoom+0.0008,1.1)",
        "x_expr": "(iw-iw/zoom)*(on/124)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s1-shot4",
        "src": "s1-shot4.png",
        "vo": (
            "Een portaal! Groot, paars, en het trok gewoon... aan me. Alsof het wist dat ik zou komen. "
            "Zou jij naar binnen durven? Typ 'JA' in de comments als jij ook zo dapper bent als ik!"
        ),
        "z_expr": "if(eq(on,0),1.18,max(zoom-0.0014,1.0))",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
]


def synthesize(text, dest_wav):
    cmd = [PIPER_PY, "-m", "piper", "--model", VOICE_MODEL, "--output_file", dest_wav]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)


def wav_duration(path):
    with wave.open(path, "rb") as f:
        return f.getnframes() / f.getframerate()


def build_filter(shot):
    d = shot["_frames"]
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
        "-vf", vf, "-t", str(shot["duration"]),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", dest,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


def concat_media(paths, dest, is_audio):
    list_path = os.path.join(OUT_DIR, "_concat_list.txt")
    with open(list_path, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    codec = ["-c:a", "pcm_s16le"] if is_audio else ["-c", "copy"]
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path, *codec, dest]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(list_path)


def make_silence(dest, duration):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
        "-t", str(duration), "-c:a", "pcm_s16le", dest,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Synthesizing per-shot voice-over segments...")
    for shot in SHOTS:
        wav_path = os.path.join(OUT_DIR, f"{shot['name']}_vo.wav")
        synthesize(shot["vo"], wav_path)
        vo_dur = wav_duration(wav_path)
        shot["duration"] = round(vo_dur + PAD_SECONDS, 2)
        shot["_frames"] = int(shot["duration"] * FPS)
        shot["_vo_wav"] = wav_path
        print(f"  {shot['name']}: vo={vo_dur:.1f}s -> clip={shot['duration']}s")

    print("Rendering pan/zoom clips...")
    video_clips = [make_clip(s) for s in SHOTS]

    print("Assembling audio track (voice-over + trailing pad silence per shot)...")
    audio_parts = []
    for shot in SHOTS:
        audio_parts.append(shot["_vo_wav"])
        silence_path = os.path.join(OUT_DIR, f"{shot['name']}_pad.wav")
        make_silence(silence_path, PAD_SECONDS)
        audio_parts.append(silence_path)
    audio_track = os.path.join(OUT_DIR, "s1_voiceover_full.wav")
    concat_media(audio_parts, audio_track, is_audio=True)

    print("Concatenating video...")
    video_track = os.path.join(OUT_DIR, "episode01_scene1_video_only.mp4")
    concat_media(video_clips, video_track, is_audio=False)

    print("Muxing...")
    final = os.path.join(OUT_DIR, "episode01_scene1_vo.mp4")
    cmd = [
        FFMPEG, "-y", "-i", video_track, "-i", audio_track,
        "-c:v", "copy", "-c:a", "aac", "-shortest", final,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    for shot in SHOTS:
        os.remove(shot["_vo_wav"])
        os.remove(os.path.join(OUT_DIR, f"{shot['name']}_pad.wav"))

    print(f"Done -> {final}")
