"""Scene 1 preview, English voice-over (Piper) + burned-in subtitles.

Same per-shot sync approach as make_scene1_video.py (clip length is driven
by that shot's own VO segment), but in English, and it additionally writes
an .srt and burns it into the final video with ffmpeg's subtitles filter.

Usage:
    python make_scene1_video_en.py
"""
import os
import subprocess
import wave

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
VOICE_MODEL = r"C:\Users\Isaak\nobi\production\voices\en_US-amy-medium.onnx"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
PIPER_PY = r"C:\Users\Isaak\ComfyUI\venv\Scripts\python.exe"
FPS = 25
W, H = 1920, 1080
PAD_SECONDS = 0.6

SHOTS = [
    {
        "name": "s1-shot1",
        "src": "s1-shot1.png",
        "vo": "It all started this morning. I was just harvesting my carrots... a totally normal morning...",
        "sub": "It all started this morning. I was just harvesting\nmy carrots... a totally normal morning...",
        "z_expr": "min(zoom+0.0012,1.15)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)*0.85",
    },
    {
        "name": "s1-shot2",
        "src": "s1-shot2_closeup_crop.png",
        "vo": "When I heard this.",
        "sub": "When I heard this.",
        "z_expr": "min(zoom+0.0022,1.2)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
        "pad": True,
    },
    {
        "name": "s1-shot3",
        "src": "s1-shot3.png",
        "vo": "I walked into the forest, and then I saw it.",
        "sub": "I walked into the forest, and then I saw it.",
        "z_expr": "min(zoom+0.0008,1.1)",
        "x_expr": "(iw-iw/zoom)*(on/124)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s1-shot4",
        "src": "s1-shot4.png",
        "vo": (
            "A portal! Big, purple, and it was just... pulling me in. Like it knew I was coming. "
            "Would you dare go inside? Type 'YES' in the comments if you're as brave as me!"
        ),
        "sub": (
            "A portal! Big, purple, and it was just... pulling me in.\n"
            "Like it knew I was coming.|"
            "Would you dare go inside?\nType 'YES' in the comments if you're as brave as me!"
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
    dest = os.path.join(OUT_DIR, f"{shot['name']}_panzoom_en.mp4")
    vf = build_filter(shot)
    cmd = [
        FFMPEG, "-y", "-loop", "1", "-i", src,
        "-vf", vf, "-t", str(shot["duration"]),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", dest,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dest


def concat_media(paths, dest, is_audio):
    list_path = os.path.join(OUT_DIR, "_concat_list_en.txt")
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


def srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(shots, dest_path):
    """Split each shot's caption on '|' into separate cues sharing that
    shot's on-screen time evenly -- keeps long shot4 lines from sitting on
    screen as one big wall of text for its full ~18s duration."""
    entries = []
    t = 0.0
    for shot in shots:
        parts = shot["sub"].split("|")
        span = shot["_vo_dur"]
        part_dur = span / len(parts)
        for i, part in enumerate(parts):
            start = t + i * part_dur
            end = t + (i + 1) * part_dur
            entries.append((start, end, part))
        t += shot["duration"]

    with open(dest_path, "w", encoding="utf-8") as f:
        for i, (start, end, text) in enumerate(entries, 1):
            f.write(f"{i}\n{srt_timestamp(start)} --> {srt_timestamp(end)}\n{text}\n\n")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Synthesizing English voice-over segments...")
    for shot in SHOTS:
        wav_path = os.path.join(OUT_DIR, f"{shot['name']}_vo_en.wav")
        synthesize(shot["vo"], wav_path)
        vo_dur = wav_duration(wav_path)
        shot["_vo_dur"] = vo_dur
        shot["duration"] = round(vo_dur + PAD_SECONDS, 2)
        shot["_frames"] = int(shot["duration"] * FPS)
        shot["_vo_wav"] = wav_path
        print(f"  {shot['name']}: vo={vo_dur:.1f}s -> clip={shot['duration']}s")

    print("Rendering pan/zoom clips...")
    video_clips = [make_clip(s) for s in SHOTS]

    print("Assembling audio track...")
    audio_parts = []
    for shot in SHOTS:
        audio_parts.append(shot["_vo_wav"])
        silence_path = os.path.join(OUT_DIR, f"{shot['name']}_pad_en.wav")
        make_silence(silence_path, PAD_SECONDS)
        audio_parts.append(silence_path)
    audio_track = os.path.join(OUT_DIR, "s1_voiceover_en.wav")
    concat_media(audio_parts, audio_track, is_audio=True)

    print("Concatenating video...")
    video_track = os.path.join(OUT_DIR, "episode01_scene1_video_only_en.mp4")
    concat_media(video_clips, video_track, is_audio=False)

    print("Writing subtitles...")
    srt_path = os.path.join(OUT_DIR, "episode01_scene1_en.srt")
    write_srt(SHOTS, srt_path)

    print("Muxing audio...")
    with_audio = os.path.join(OUT_DIR, "_episode01_scene1_en_noSubs.mp4")
    cmd = [
        FFMPEG, "-y", "-i", video_track, "-i", audio_track,
        "-c:v", "copy", "-c:a", "aac", "-shortest", with_audio,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    print("Burning in subtitles...")
    final = os.path.join(OUT_DIR, "episode01_scene1_en.mp4")
    srt_ffmpeg_path = srt_path.replace("\\", "/").replace(":", "\\:")
    style = "FontName=Arial,FontSize=13,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=60"
    vf = f"subtitles='{srt_ffmpeg_path}':force_style='{style}'"
    cmd = [
        FFMPEG, "-y", "-i", with_audio, "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "copy", final,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    for shot in SHOTS:
        os.remove(shot["_vo_wav"])
        os.remove(os.path.join(OUT_DIR, f"{shot['name']}_pad_en.wav"))
    os.remove(with_audio)

    print(f"Done -> {final}")
