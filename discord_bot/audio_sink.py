"""Per-user audio sink for discord-ext-voice-recv.

Receives 48 kHz stereo 16-bit PCM from Discord, downsamples to 16 kHz mono
on the fly (6x reduction), and buffers (timestamp_ms, pcm) tuples in memory.
"""
from __future__ import annotations

import array
import time
from typing import Optional

import discord
from discord.ext import voice_recv


def _downsample(pcm: bytes) -> bytes:
    """48 kHz stereo 16-bit → 16 kHz mono 16-bit (naive 3:1 + left channel)."""
    shorts: array.array = array.array('h')
    shorts.frombytes(pcm)
    # Stereo interleaved: L0 R0 L1 R1 ...  Take left channel every 3rd frame.
    mono = array.array('h', (shorts[i * 2] for i in range(0, len(shorts) // 2, 3)))
    return mono.tobytes()


class SessionSink(voice_recv.AudioSink):
    """Collects speaking audio per user with session-relative timestamps."""

    SAMPLE_RATE = 16_000  # after downsampling
    CHANNELS = 1
    SAMPLE_WIDTH = 2  # bytes, 16-bit

    def __init__(self) -> None:
        self._start: float = time.monotonic()
        # uid -> list of (timestamp_ms, downsampled_pcm)
        self._chunks: dict[int, list[tuple[int, bytes]]] = {}
        self._names: dict[int, str] = {}

    # ── AudioSink interface ────────────────────────────────────────────────

    def wants_opus(self) -> bool:
        return False

    def write(self, user: Optional[discord.Member], data: voice_recv.VoiceData) -> None:
        if user is None:
            return
        uid = user.id
        if uid not in self._chunks:
            self._chunks[uid] = []
            self._names[uid] = user.display_name
        ts_ms = int((time.monotonic() - self._start) * 1000)
        self._chunks[uid].append((ts_ms, _downsample(data.pcm)))

    def cleanup(self) -> None:
        pass  # nothing to close — all data is in memory

    # ── Accessors ─────────────────────────────────────────────────────────

    @property
    def user_names(self) -> dict[int, str]:
        return dict(self._names)

    @property
    def chunks(self) -> dict[int, list[tuple[int, bytes]]]:
        """uid -> [(timestamp_ms, pcm_bytes), ...]"""
        return self._chunks

    def session_duration_ms(self) -> int:
        return int((time.monotonic() - self._start) * 1000)
