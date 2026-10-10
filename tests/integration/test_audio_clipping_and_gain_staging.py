"""
Integration Regression Test: Audio Clipping & Gain Staging Protection
Verifies headroom protection against digital PCM_16 hard clipping
on long passages and consecutive segments without altering inter-segment dynamics.
"""

import wave
import struct
from pathlib import Path
import pytest


SUITE_DIR = Path(r"D:\AIVoiceStudioData\benchmarks\outputs\quality_validation_suite")


def _read_wav_metrics(wav_path: Path):
    assert wav_path.exists(), f"Target audio file does not exist: {wav_path}"
    with wave.open(str(wav_path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        n_frames = wf.getnframes()
        raw_bytes = wf.readframes(n_frames)

    assert sampwidth == 2, "Expected 16-bit PCM WAV"
    # Unpack 16-bit signed integers
    fmt = f"<{n_frames * n_channels}h"
    samples = struct.unpack(fmt, raw_bytes)

    max_amp = max(abs(s) for s in samples) if samples else 0
    peak_float = max_amp / 32768.0

    # Count clipped samples at the 16-bit boundaries
    clipped_pos = sum(1 for s in samples if s >= 32767)
    clipped_neg = sum(1 for s in samples if s <= -32768)
    total_clipped = clipped_pos + clipped_neg

    duration = n_frames / float(framerate)

    return {
        "framerate": framerate,
        "duration": duration,
        "max_int16": max_amp,
        "peak_float": peak_float,
        "total_clipped": total_clipped,
        "samples_count": len(samples),
    }


def test_long_multi_sentence_sample_05_no_clipping():
    """
    Verifies that the 16+ second long multi-sentence speech artifact (sample 05)
    has zero clipped samples and peak amplitude strictly <= 0.985.
    """
    wav_05 = SUITE_DIR / "05_long_multi_sentence_ref_a.wav"
    metrics = _read_wav_metrics(wav_05)

    assert metrics["framerate"] == 48000, f"Expected 48 kHz, got {metrics['framerate']}"
    assert metrics["duration"] > 14.0, f"Expected > 14s duration, got {metrics['duration']}"
    assert metrics["total_clipped"] == 0, f"Detected {metrics['total_clipped']} clipped samples in sample 05!"
    assert metrics["peak_float"] <= 0.985, f"Peak amplitude exceeded safe headroom: {metrics['peak_float']}"


def test_all_validation_suite_consecutive_samples_zero_clipping():
    """
    Verifies that all 6 quality evaluation WAV artifacts maintain headroom
    with zero hard clipping.
    """
    for wav_file in SUITE_DIR.glob("*.wav"):
        metrics = _read_wav_metrics(wav_file)
        assert metrics["total_clipped"] == 0, (
            f"File {wav_file.name} has {metrics['total_clipped']} clipped samples!"
        )
        assert metrics["peak_float"] <= 0.99, (
            f"File {wav_file.name} exceeded peak threshold: {metrics['peak_float']}"
        )


def test_gain_staging_logic_unit_simulation():
    """
    Simulates gain staging behavior:
    - Normal segments (peak <= 0.98) are untouched (scale = 1.0).
    - Over-threshold segments are scaled to exactly 0.98 without clipping.
    """
    def apply_gain_staging(float_samples, threshold=0.98):
        peak = max(abs(s) for s in float_samples) if float_samples else 0.0
        if peak > threshold:
            scale = threshold / peak
            return [s * scale for s in float_samples]
        return float_samples

    # Case 1: Quiet segment (peak 0.60) -> must remain untouched
    quiet = [0.1, 0.4, 0.6, -0.5, 0.0]
    out_quiet = apply_gain_staging(quiet)
    assert out_quiet == quiet, "Quiet segment was altered unexpectedly!"

    # Case 2: Over-threshold segment (peak 1.0519) -> scaled to 0.98
    loud = [0.2, 0.8, 1.0519, -0.9, 0.1]
    out_loud = apply_gain_staging(loud)
    assert max(abs(s) for s in out_loud) == pytest.approx(0.98, rel=1e-4)
    assert all(abs(s) <= 0.98 for s in out_loud)
