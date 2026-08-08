"""Scene 2 (portal touch + Pixa's introduction), English voice-over via
Kokoro + burned-in subtitles. Same per-shot sync approach as Scene 1.

Shot4 carries two speakers -- Nobi narrating, then Pixa's distorted robot
voice -- synthesized as two separate clips (different Kokoro voice for
Pixa, plus an ffmpeg pitch/tremolo/bandpass chain for the "vervormde
robotstem" effect from the script) and concatenated for that shot's track.

Run with the TTS venv:
    production/tts_venv/Scripts/python.exe make_scene2_video.py
"""
import os
import subprocess
import numpy as np
import soundfile as sf
from kokoro import KPipeline

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
NOBI_VOICE = "am_adam"
PIXA_VOICE = "af_bella"
SAMPLE_RATE = 24000
FPS = 25
W, H = 1920, 1080
PAD_SECONDS = 0.6
GAP_SECONDS = 0.35  # between Nobi's and Pixa's lines within shot4

SHOTS = [
    {
        "name": "s2-shot1",
        "src": "s2-shot1.png",
        "lines": [("nobi", "I put my hand on the portal and—")],
        "sub": "I put my hand on the portal and—",
        "z_expr": "min(zoom+0.0015,1.15)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s2-shot2",
        "src": "s2-shot2.png",
        "lines": [("nobi", "WHAT IS THAT?!")],
        "sub": "WHAT IS THAT?!",
        "z_expr": "min(zoom+0.003,1.2)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s2-shot3",
        "src": "s2-shot3.png",
        "lines": [("nobi", "A little robot! She calls herself Pixa.")],
        "sub": "A little robot! She calls herself Pixa.",
        "z_expr": "min(zoom+0.0012,1.12)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
    {
        "name": "s2-shot4",
        "src": "s2-shot4.png",
        "lines": [
            ("nobi", "She says the portal leads to a floating island, full of hidden crystals. But there's a catch..."),
            ("pixa", "The island... is falling apart. Only ten minutes... before it's gone."),
        ],
        "sub": (
            "She says the portal leads to a floating island,\nfull of hidden crystals. But there's a catch...|"
            "PIXA: The island... is falling apart.\nOnly ten minutes... before it's gone."
        ),
        "z_expr": "min(zoom+0.0008,1.1)",
        "x_expr": "iw/2-(iw/zoom/2)",
        "y_expr": "ih/2-(ih/zoom/2)",
    },
]


def synth_line(pipeline, voice, text, dest_wav):
    chunks = [audio for _, _, audio in pipeline(text, voice=voice)]
    audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
    sf.write(dest_wav, audio, SAMPLE_RATE)
    return len(audio) / SAMPLE_RATE


def robotize(src_wav, dest_wav):
    af = (
        "asetrate=24000*0.88,aresample=24000,atempo=1.12,"
        "tremolo=f=28:d=0.55,"
        "highpass=f=280,lowpass=f=3600"
    )
    cmd = [FFMPEG, "-y", "-i", src_wav, "-af", af, dest_wav]
    subprocess.run(cmd, check=True, capture_output=True)


def wav_duration(path):
    import wave
    with wave.open(path, "rb") as f:
        return f.getnframes() / f.getframerate()


def make_silence(dest, duration):
    cmd = [
        FFMPEG, "-y", "-f", "lavfi", "-i", f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-t", str(max(duration, 0.05)), "-c:a", "pcm_s16le", dest,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def build_filter(shot):
    d = shot["_frames"]
    return (
        "scale=8000:-1,"
        f"zoompan=z='{shot['z_expr']}':d={d}:x='{shot['x_expr']}':y='{shot['y_expr']}'"
        f":s={W}x{H}:fps={FPS},format=yuv420p"
    )


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
    list_path = os.path.join(OUT_DIR, "_concat_list_s2.txt")
    with open(list_path, "w") as f:
        for p in paths:
            f.write(f"file '{p}'\n")
    codec = ["-c:a", "pcm_s16le"] if is_audio else ["-c", "copy"]
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path, *codec, dest]
    subprocess.run(cmd, check=True, capture_output=True)
    os.remove(list_path)


def srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(shots, dest_path):
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
    pipeline = KPipeline(lang_code="a")

    print("Synthesizing voice-over...")
    for shot in SHOTS:
        line_wavs = []
        total_dur = 0.0
        for j, (speaker, text) in enumerate(shot["lines"]):
            voice = NOBI_VOICE if speaker == "nobi" else PIXA_VOICE
            raw_wav = os.path.join(OUT_DIR, f"{shot['name']}_line{j}_raw.wav")
            dur = synth_line(pipeline, voice, text, raw_wav)
            if speaker == "pixa":
                fx_wav = os.path.join(OUT_DIR, f"{shot['name']}_line{j}.wav")
                robotize(raw_wav, fx_wav)
                os.remove(raw_wav)
                dur = wav_duration(fx_wav)
                line_wavs.append(fx_wav)
            else:
                line_wavs.append(raw_wav)
            total_dur += dur
            if j < len(shot["lines"]) - 1:
                gap_wav = os.path.join(OUT_DIR, f"{shot['name']}_gap{j}.wav")
                make_silence(gap_wav, GAP_SECONDS)
                line_wavs.append(gap_wav)
                total_dur += GAP_SECONDS

        combined = os.path.join(OUT_DIR, f"{shot['name']}_vo.wav")
        if len(line_wavs) > 1:
            concat_media(line_wavs, combined, is_audio=True)
            for p in line_wavs:
                os.remove(p)
        else:
            os.replace(line_wavs[0], combined)

        shot["_vo_dur"] = total_dur
        shot["duration"] = round(total_dur + PAD_SECONDS, 2)
        shot["_frames"] = int(shot["duration"] * FPS)
        shot["_vo_wav"] = combined
        print(f"  {shot['name']}: vo={total_dur:.1f}s -> clip={shot['duration']}s")

    print("Rendering pan/zoom clips...")
    video_clips = [make_clip(s) for s in SHOTS]

    print("Assembling audio track...")
    audio_parts = []
    for shot in SHOTS:
        audio_parts.append(shot["_vo_wav"])
        pad_path = os.path.join(OUT_DIR, f"{shot['name']}_pad.wav")
        make_silence(pad_path, PAD_SECONDS)
        audio_parts.append(pad_path)
    audio_track = os.path.join(OUT_DIR, "s2_voiceover.wav")
    concat_media(audio_parts, audio_track, is_audio=True)

    print("Concatenating video...")
    video_track = os.path.join(OUT_DIR, "episode01_scene2_video_only.mp4")
    concat_media(video_clips, video_track, is_audio=False)

    print("Writing subtitles...")
    srt_path = os.path.join(OUT_DIR, "episode01_scene2_en.srt")
    write_srt(SHOTS, srt_path)

    print("Muxing audio...")
    with_audio = os.path.join(OUT_DIR, "_episode01_scene2_noSubs.mp4")
    cmd = [
        FFMPEG, "-y", "-i", video_track, "-i", audio_track,
        "-c:v", "copy", "-c:a", "aac", "-shortest", with_audio,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    print("Burning in subtitles...")
    final = os.path.join(OUT_DIR, "episode01_scene2_en.mp4")
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
        os.remove(os.path.join(OUT_DIR, f"{shot['name']}_pad.wav"))
        os.remove(os.path.join(OUT_DIR, f"{shot['name']}_panzoom.mp4"))
    os.remove(with_audio)
    os.remove(video_track)
    os.remove(audio_track)

    print(f"Done -> {final}")
