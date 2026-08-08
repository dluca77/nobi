"""Synthesize a handful of simple sound effects (whoosh, confetti pop, warm
chime) with numpy/scipy -- no external SFX library needed, no network
fetch, so no risk of pulling in a low-quality/unlicensed random file.

Usage:
    python make_sfx.py
"""
import os
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

OUT_DIR = r"C:\Users\Isaak\nobi\production\sfx"
SR = 44100


def bandpass_noise(duration, low, high, sr=SR):
    n = int(duration * sr)
    noise = np.random.randn(n)
    sos = butter(4, [low, high], btype="band", fs=sr, output="sos")
    return sosfilt(sos, noise)


def envelope(n, attack, release, curve=2.0):
    env = np.ones(n)
    a = int(attack * n)
    r = int(release * n)
    if a > 0:
        env[:a] = np.linspace(0, 1, a) ** curve
    if r > 0:
        env[-r:] = np.linspace(1, 0, r) ** curve
    return env


def save(path, audio, sr=SR):
    audio = np.clip(audio, -1, 1)
    wavfile.write(path, sr, (audio * 32767).astype(np.int16))
    print("saved", path)


def make_whoosh(dest, duration=0.9):
    n = int(duration * SR)
    t = np.linspace(0, 1, n)
    layers = [
        (bandpass_noise(duration, 150, 500), np.exp(-((t - 0.15) ** 2) / (2 * 0.12 ** 2))),
        (bandpass_noise(duration, 500, 1800), np.exp(-((t - 0.35) ** 2) / (2 * 0.15 ** 2))),
        (bandpass_noise(duration, 1800, 5000), np.exp(-((t - 0.55) ** 2) / (2 * 0.18 ** 2))),
        (bandpass_noise(duration, 4000, 9000), np.exp(-((t - 0.75) ** 2) / (2 * 0.2 ** 2))),
    ]
    mix = sum(sig * env for sig, env in layers)
    mix = mix / np.max(np.abs(mix))
    mix *= envelope(n, 0.02, 0.35, curve=1.5) * 0.8
    save(dest, mix)


def make_pop(dest, duration=0.35):
    n = int(duration * SR)
    t = np.arange(n) / SR
    freq = 900 * np.exp(-t * 18) + 200
    phase = 2 * np.pi * np.cumsum(freq) / SR
    tone = np.sin(phase) * np.exp(-t * 22)
    sparkle_dur = duration
    sparkle = bandpass_noise(sparkle_dur, 3000, 12000) * np.exp(-t * 9) * 0.5
    mix = tone * 0.9 + sparkle
    mix = mix / np.max(np.abs(mix)) * 0.85
    save(dest, mix)


def make_chime(dest, duration=2.2):
    n = int(duration * SR)
    t = np.arange(n) / SR
    freqs = [523.25, 659.25, 783.99, 1046.5]  # C5 E5 G5 C6 major chord
    mix = np.zeros(n)
    for i, f in enumerate(freqs):
        delay = i * 0.09
        d_n = int(delay * SR)
        decay = np.exp(-t * (1.1 + i * 0.15))
        tone = np.sin(2 * np.pi * f * t) * decay
        tone = np.roll(tone, d_n)
        tone[:d_n] = 0
        mix += tone * (0.35 - i * 0.03)
    mix = mix / np.max(np.abs(mix)) * 0.7
    mix *= envelope(n, 0.01, 0.7, curve=1.0)
    save(dest, mix)


def make_magic_sparkle(dest, duration=1.2):
    n = int(duration * SR)
    t = np.arange(n) / SR
    mix = np.zeros(n)
    rng = np.random.default_rng(7)
    for _ in range(14):
        start = rng.uniform(0, duration * 0.6)
        f = rng.uniform(1200, 3200)
        dur = rng.uniform(0.15, 0.35)
        local_t = t - start
        env = np.where((local_t >= 0) & (local_t < dur), np.exp(-local_t * 14), 0)
        mix += np.sin(2 * np.pi * f * local_t) * env
    mix = mix / np.max(np.abs(mix)) * 0.6
    save(dest, mix)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    make_whoosh(os.path.join(OUT_DIR, "whoosh.wav"))
    make_pop(os.path.join(OUT_DIR, "confetti_pop.wav"))
    make_chime(os.path.join(OUT_DIR, "warm_chime.wav"))
    make_magic_sparkle(os.path.join(OUT_DIR, "magic_sparkle.wav"))
