"""Local Whisper transcription via faster-whisper.

Each user's speaking chunks are processed individually — no silence padding,
no chunking, no API calls. The session-relative timestamp stored at record
time is added to Whisper's segment-level offsets to reconstruct the timeline.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

import numpy as np
from faster_whisper import WhisperModel

log = logging.getLogger('orpheus.transcribe')

# Override with WHISPER_MODEL env var: tiny / base / small / medium / large-v3
MODEL_SIZE = os.environ.get('WHISPER_MODEL', 'medium')

# Use 'auto' to let faster-whisper pick the best device (CUDA > MPS > CPU).
# On Apple Silicon this will use CPU with optimised AVX2 kernels via CTranslate2.
DEVICE = os.environ.get('WHISPER_DEVICE', 'auto')
COMPUTE_TYPE = os.environ.get('WHISPER_COMPUTE', 'default')

SAMPLE_RATE = 16_000  # must match audio_sink.py


@lru_cache(maxsize=1)
def _get_model() -> WhisperModel:
    log.info('Loading Whisper model "%s" on device "%s"...', MODEL_SIZE, DEVICE)
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    log.info('Model ready.')
    return model


def _pcm_to_float(pcm: bytes) -> np.ndarray:
    """Convert 16-bit signed PCM bytes to float32 in [-1.0, 1.0]."""
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0


# Target RMS for normalized speech (~ -26 dBFS) and the ceiling normalization
# is allowed to push peaks to (leaves headroom so normalizing can't itself
# introduce new clipping).
_TARGET_RMS = 0.05
_PEAK_CEILING = 0.95


def _normalize_audio(audio: np.ndarray) -> np.ndarray:
    """Bring audio to a consistent level regardless of a player's input gain.

    Discord applies each player's own client-side AGC/noise suppression
    before a bot ever sees the audio, and neither can be adjusted server-side
    or per-guild — a hot mic reaches us already clipped. This can't undo
    clipping that already happened, but normalizing every speaker to the same
    target level (instead of relying on everyone's mic gain being reasonable)
    is the one lever that works uniformly regardless of individual settings.
    """
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < 1e-6:
        return audio  # silence — nothing to normalize
    normalized = audio * (_TARGET_RMS / rms)
    peak = np.max(np.abs(normalized))
    if peak > _PEAK_CEILING:
        normalized *= _PEAK_CEILING / peak
    return normalized


# A speaker whose raw (pre-normalization) audio clips this much of the time
# is likely coming from an overdriven mic — worth a nudge to that one player.
_CLIP_WARNING_RATIO = 0.015


def _transcribe_segment(
    model: WhisperModel,
    audio: np.ndarray,
    session_offset_s: float,
    language: str = 'en',
    initial_prompt: str | None = None,
) -> list[tuple[float, float, str]]:
    """Transcribe one contiguous audio chunk.

    Returns [(abs_start_s, abs_end_s, text), ...] with timestamps relative
    to session start (session_offset_s already added).
    """
    if len(audio) < SAMPLE_RATE * 0.5:  # skip clips under 0.5 s
        return []

    audio = _normalize_audio(audio)

    segments, _ = model.transcribe(
        audio,
        language=language,
        beam_size=5,
        vad_filter=True,          # skip internal silence
        vad_parameters={'min_silence_duration_ms': 300},
        initial_prompt=initial_prompt,
    )
    results = []
    for seg in segments:
        # Whisper hallucinates boilerplate ("thanks for watching", "bye") on
        # silence/noise instead of returning nothing. no_speech_prob and
        # avg_logprob are exactly the confidence signals for catching that —
        # drop segments Whisper itself flagged as unreliable.
        if seg.no_speech_prob > 0.6 or seg.avg_logprob < -1.0:
            continue
        text = seg.text.strip()
        if text:
            results.append((
                session_offset_s + seg.start,
                session_offset_s + seg.end,
                text,
            ))
    return results


def transcribe_wavs(
    chunks: dict[int, list[tuple[int, bytes]]],
    user_names: dict[int, str],
    session_duration_ms: int,  # kept for API compatibility, unused here
    progress_callback=None,  # optional: called with (completed_count, speaker_name)
    character_names: list[str] | None = None,
) -> tuple[list[tuple[float, str, str]], list[str]]:
    """Transcribe all users.

    Returns (lines, quality_warnings) where lines is sorted
    [(session_time_s, speaker, text), ...] and quality_warnings names any
    speaker whose raw audio was clipping heavily enough that it's worth a
    nudge to check their mic input volume.
    """
    model = _get_model()
    lines: list[tuple[float, str, str]] = []
    quality_warnings: list[str] = []

    initial_prompt = None
    if character_names:
        initial_prompt = (
            'Dungeons & Dragons tabletop RPG session. '
            'Character and NPC names that may come up: ' + ', '.join(character_names) + '.'
        )

    for i, (uid, user_chunks) in enumerate(chunks.items()):
        name = user_names.get(uid, f'User{uid}')
        if progress_callback:
            progress_callback(i, name)
        log.info('Transcribing %s (%d speaking chunks)...', name, len(user_chunks))

        # Group consecutive chunks into runs separated by silence > 2 s.
        # Each run is submitted to Whisper as one call to preserve context.
        runs = _group_into_runs(user_chunks, gap_threshold_ms=2000)
        log.info('  %d speaking runs for %s', len(runs), name)

        clipped_samples = 0
        total_samples = 0
        for run_offset_ms, run_pcm in runs:
            audio = _pcm_to_float(run_pcm)
            total_samples += len(audio)
            clipped_samples += int(np.sum(np.abs(audio) >= 0.999))
            segs = _transcribe_segment(model, audio, run_offset_ms / 1000, initial_prompt=initial_prompt)
            for start, _end, text in segs:
                lines.append((start, name, text))

        if total_samples and clipped_samples / total_samples > _CLIP_WARNING_RATIO:
            log.info('  %s: %.1f%% of audio was clipping', name, 100 * clipped_samples / total_samples)
            quality_warnings.append(name)

    lines.sort(key=lambda x: x[0])
    return lines, quality_warnings


def _group_into_runs(
    user_chunks: list[tuple[int, bytes]],
    gap_threshold_ms: int = 2000,
) -> list[tuple[int, bytes]]:
    """Merge consecutive speaking packets into runs.

    A new run starts when the gap between packets exceeds gap_threshold_ms.
    Returns [(run_start_ms, concatenated_pcm), ...].
    """
    if not user_chunks:
        return []

    runs: list[tuple[int, bytes]] = []
    run_start_ms, run_buf = user_chunks[0]
    prev_end_ms = run_start_ms + _pcm_duration_ms(user_chunks[0][1])

    for ts_ms, pcm in user_chunks[1:]:
        gap_ms = ts_ms - prev_end_ms
        if gap_ms > gap_threshold_ms:
            runs.append((run_start_ms, run_buf))
            run_start_ms = ts_ms
            run_buf = pcm
        else:
            run_buf += pcm
        prev_end_ms = ts_ms + _pcm_duration_ms(pcm)

    runs.append((run_start_ms, run_buf))
    return runs


def _pcm_duration_ms(pcm: bytes) -> int:
    """Duration in ms of 16 kHz mono 16-bit PCM."""
    num_samples = len(pcm) // 2  # 2 bytes per sample
    return num_samples * 1000 // SAMPLE_RATE


def format_transcript(lines: list[tuple[float, str, str]]) -> str:
    """Format as [HH:MM:SS] **Speaker**: text."""
    parts = []
    for t, name, text in lines:
        h = int(t) // 3600
        m = (int(t) % 3600) // 60
        s = int(t) % 60
        ts = f'{h:02d}:{m:02d}:{s:02d}' if h else f'{m:02d}:{s:02d}'
        parts.append(f'[{ts}] **{name}**: {text}')
    return '\n\n'.join(parts)
