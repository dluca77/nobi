"""Combine the LTX-Video motion clips with the logo/graphics overlay and
synthesized SFX into the final intro/outro deliverables.

Usage:
    python finalize_intro_outro.py
"""
import os
import subprocess

OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
SFX_DIR = r"C:\Users\Isaak\nobi\production\sfx"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"

W, H = 1920, 1080


def build(video_src, overlay_png, audio_specs, fade_in_at, fade_dur, dest):
    """audio_specs: list of (wav_path, start_offset_seconds)"""
    n_audio = len(audio_specs)
    inputs = ["-i", video_src, "-i", overlay_png]
    for wav, _ in audio_specs:
        inputs += ["-i", wav]

    # NOTE: ffmpeg's `fade` filter with alpha=1 was silently producing a
    # fully-transparent (invisible) overlay in this build regardless of
    # timing -- confirmed via isolated testing, not just a timing mistake.
    # Using a hard cut-in via overlay's `enable` timeline expression instead,
    # which is simple and reliably visible.
    filter_parts = [
        f"[0:v]scale={W}:{H}:flags=lanczos[bg]",
        f"[1:v]scale={W}:{H}[ov]",
        f"[bg][ov]overlay=0:0:enable='gte(t,{fade_in_at})'[vout]",
    ]
    audio_labels = []
    for i, (wav, offset) in enumerate(audio_specs):
        idx = i + 2
        label = f"a{i}"
        delay_ms = int(offset * 1000)
        filter_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[{label}]")
        audio_labels.append(f"[{label}]")
    filter_parts.append(f"{''.join(audio_labels)}amix=inputs={n_audio}:duration=longest:dropout_transition=0[aout]")

    filter_complex = ";".join(filter_parts)
    cmd = [
        FFMPEG, "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-t", str(video_duration(video_src)),
        dest,
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def video_duration(path):
    out = subprocess.run(
        [FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


if __name__ == "__main__":
    build(
        video_src=os.path.join(OUT_DIR, "intro_titlecard_video.mp4"),
        overlay_png=os.path.join(OUT_DIR, "nobi_world_logo.png"),
        audio_specs=[
            (os.path.join(SFX_DIR, "whoosh.wav"), 0.0),
            (os.path.join(SFX_DIR, "confetti_pop.wav"), 0.15),
        ],
        fade_in_at=0.5, fade_dur=0.4,
        dest=os.path.join(OUT_DIR, "intro_final.mp4"),
    )
    print("saved intro_final.mp4")

    # regenerate the outro overlay png fresh (build_intro_outro.py deletes its temp copy)
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from build_intro_outro import build_outro_overlay
    outro_overlay = os.path.join(OUT_DIR, "_outro_overlay_final.png")
    build_outro_overlay(outro_overlay)

    build(
        video_src=os.path.join(OUT_DIR, "outro_endscreen_video.mp4"),
        overlay_png=outro_overlay,
        audio_specs=[
            (os.path.join(SFX_DIR, "warm_chime.wav"), 0.2),
            (os.path.join(SFX_DIR, "magic_sparkle.wav"), 0.3),
        ],
        fade_in_at=0.8, fade_dur=0.5,
        dest=os.path.join(OUT_DIR, "outro_final.mp4"),
    )
    os.remove(outro_overlay)
    print("saved outro_final.mp4")
