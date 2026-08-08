"""Generate Dutch voice-over with Piper TTS and mux it onto a video.

Usage:
    python make_voiceover.py
"""
import os
import subprocess
import wave

VOICES_DIR = r"C:\Users\Isaak\nobi\production\voices"
VOICE_MODEL = os.path.join(VOICES_DIR, "nl_NL-mls-medium.onnx")
OUT_DIR = r"C:\Users\Isaak\nobi\production\output"
FFMPEG = r"C:\Users\Isaak\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0-full_build\bin\ffmpeg.exe"
PIPER_PY = r"C:\Users\Isaak\ComfyUI\venv\Scripts\python.exe"

SCENE1_VO = (
    "Het begon allemaal vanmorgen. "
    "Ik was gewoon mijn wortels aan het oogsten... heel normaal ochtendje... toen ik dit hoorde. "
    "Ik liep het bos in, en toen zag ik het. Een portaal! Groot, paars, en het trok gewoon... aan me. "
    "Alsof het wist dat ik zou komen. "
    "Zou jij naar binnen durven? Typ 'JA' in de comments als jij ook zo dapper bent als ik!"
)


def synthesize(text, dest_wav):
    cmd = [
        PIPER_PY, "-m", "piper",
        "--model", VOICE_MODEL,
        "--output_file", dest_wav,
    ]
    subprocess.run(cmd, input=text.encode("utf-8"), check=True, capture_output=True)


def wav_duration(path):
    with wave.open(path, "rb") as f:
        return f.getnframes() / f.getframerate()


def mux(video_path, audio_path, dest_path):
    video_dur = float(subprocess.run(
        [FFMPEG.replace("ffmpeg.exe", "ffprobe.exe"), "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", video_path],
        check=True, capture_output=True, text=True,
    ).stdout.strip())
    audio_dur = wav_duration(audio_path)
    print(f"video={video_dur:.1f}s audio={audio_dur:.1f}s")

    if audio_dur > video_dur:
        # freeze the last frame to cover the extra voice-over time instead of
        # cutting the narration off
        tpad = audio_dur - video_dur + 0.5
        vf = f"tpad=stop_mode=clone:stop_duration={tpad}"
        cmd = [
            FFMPEG, "-y", "-i", video_path, "-i", audio_path,
            "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-shortest", dest_path,
        ]
    else:
        cmd = [
            FFMPEG, "-y", "-i", video_path, "-i", audio_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest", dest_path,
        ]
    subprocess.run(cmd, check=True, capture_output=True)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    wav_path = os.path.join(OUT_DIR, "s1_voiceover.wav")
    print("Synthesizing Scene 1 voice-over...")
    synthesize(SCENE1_VO, wav_path)
    print(f"  saved -> {wav_path} ({wav_duration(wav_path):.1f}s)")

    video_in = os.path.join(OUT_DIR, "episode01_scene1_preview.mp4")
    video_out = os.path.join(OUT_DIR, "episode01_scene1_preview_vo.mp4")
    print("Muxing onto preview video...")
    mux(video_in, wav_path, video_out)
    print(f"  saved -> {video_out}")
