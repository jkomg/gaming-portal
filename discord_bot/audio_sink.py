"""Per-user audio sink for discord-ext-voice-recv.

Receives 48 kHz stereo 16-bit PCM from Discord, downsamples to 16 kHz mono,
and writes each packet to disk immediately in a compact binary format:

    sessions/<session_id>/<uid>_<name>.lsm
    sessions/<session_id>/meta.json

Each .lsm file is a stream of:
    [timestamp_ms: uint32][pcm_len: uint32][pcm: bytes]

This means audio survives container restarts — the session can be
reprocessed from disk even if the bot dies mid-recording.
"""
from __future__ import annotations

import json
import os
import struct
import time
from pathlib import Path
from typing import Optional

import discord
import numpy as np
from discord.ext import voice_recv

SESSIONS_DIR = Path(os.environ.get('SESSIONS_DIR', '/app/sessions'))


def _design_lowpass_kernel(taps: int, cutoff_ratio: float) -> np.ndarray:
    """Windowed-sinc FIR low-pass kernel. cutoff_ratio = fc / (fs/2)."""
    n = np.arange(taps) - (taps - 1) / 2
    h = np.sinc(cutoff_ratio * n) * cutoff_ratio
    h *= np.hamming(taps)
    h /= h.sum()
    return h.astype(np.float32)


# 48 kHz -> 16 kHz is a 3:1 decimation, so the anti-alias cutoff is 8 kHz,
# i.e. 1/3 of the original Nyquist (24 kHz).
_LOWPASS_KERNEL = _design_lowpass_kernel(taps=63, cutoff_ratio=1 / 3)


def _downsample(pcm: bytes) -> bytes:
    """48 kHz stereo 16-bit -> 16 kHz mono 16-bit (left channel, anti-aliased).

    Decimating 3:1 without a low-pass filter first folds high-frequency
    content back into the audible band as noise, degrading intelligibility
    enough to make Whisper hallucinate instead of transcribing real speech.
    """
    shorts = np.frombuffer(pcm, dtype=np.int16)
    left = shorts[0::2].astype(np.float32)
    filtered = np.convolve(left, _LOWPASS_KERNEL, mode='same')
    decimated = np.clip(filtered[::3], -32768, 32767).astype(np.int16)
    return decimated.tobytes()


class SessionSink(voice_recv.AudioSink):
    """Streams speaking audio per user to disk with session-relative timestamps."""

    SAMPLE_RATE = 16_000
    CHANNELS = 1
    SAMPLE_WIDTH = 2

    def __init__(self, session_id: str) -> None:
        self._start: float = time.monotonic()
        self._session_dir: Path = SESSIONS_DIR / session_id
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[int, object] = {}   # uid -> open file handle
        self._names: dict[int, str] = {}

    # ── AudioSink interface ────────────────────────────────────────────────

    def wants_opus(self) -> bool:
        return False

    def write(self, user: Optional[discord.Member], data: voice_recv.VoiceData) -> None:
        if user is None:
            return
        uid = user.id
        if uid not in self._files:
            safe_name = ''.join(c if c.isalnum() or c in '-_' else '_'
                                for c in user.display_name)
            path = self._session_dir / f'{uid}_{safe_name}.lsm'
            self._files[uid] = open(path, 'ab')
            self._names[uid] = user.display_name

        ts_ms = int((time.monotonic() - self._start) * 1000)
        pcm = _downsample(data.pcm)
        header = struct.pack('<II', ts_ms, len(pcm))
        fh = self._files[uid]
        fh.write(header + pcm)
        fh.flush()  # ensure data hits disk even if we crash

    def cleanup(self) -> None:
        for fh in self._files.values():
            try:
                fh.close()
            except Exception:
                pass

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def user_names(self) -> dict[int, str]:
        return dict(self._names)

    @property
    def session_dir(self) -> Path:
        return self._session_dir

    def session_duration_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)

    def save_meta(self, campaign: str, campaign_id: int, started_at: str) -> None:
        meta = {
            'campaign': campaign,
            'campaign_id': campaign_id,
            'started_at': started_at,
            'user_names': {str(uid): name for uid, name in self._names.items()},
        }
        (self._session_dir / 'meta.json').write_text(json.dumps(meta, indent=2))


# ── Disk reader (for transcription) ───────────────────────────────────────────

def load_session(session_dir: Path) -> tuple[dict[int, list[tuple[int, bytes]]], dict[int, str]]:
    """Read .lsm files back into memory for transcription.

    Returns (chunks, user_names) in the same format SessionSink.chunks used to.
    """
    chunks: dict[int, list[tuple[int, bytes]]] = {}
    user_names: dict[int, str] = {}

    meta_path = session_dir / 'meta.json'
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        user_names = {int(uid): name for uid, name in meta.get('user_names', {}).items()}

    for lsm in sorted(session_dir.glob('*.lsm')):
        # filename: <uid>_<name>.lsm
        uid = int(lsm.stem.split('_')[0])
        packets: list[tuple[int, bytes]] = []
        data = lsm.read_bytes()
        offset = 0
        while offset + 8 <= len(data):
            ts_ms, pcm_len = struct.unpack_from('<II', data, offset)
            offset += 8
            if offset + pcm_len > len(data):
                break
            pcm = data[offset:offset + pcm_len]
            offset += pcm_len
            packets.append((ts_ms, pcm))
        if packets:
            chunks[uid] = packets
            if uid not in user_names:
                user_names[uid] = lsm.stem.split('_', 1)[1] if '_' in lsm.stem else lsm.stem

    return chunks, user_names
