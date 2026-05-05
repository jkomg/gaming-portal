"""Diagnostic tool for Orpheus session audio.

Importable by status_api, or run standalone:

    python diagnose_session.py /app/sessions/<session_id>
    python diagnose_session.py /app/sessions/<session_id> --wav
"""
from __future__ import annotations

import array
import json
import math
import struct
import wave
from pathlib import Path

SAMPLE_RATE = 16_000  # must match audio_sink.py


def _read_lsm(path: Path) -> list[tuple[int, bytes]]:
    packets = []
    data = path.read_bytes()
    offset = 0
    while offset + 8 <= len(data):
        ts_ms, pcm_len = struct.unpack_from('<II', data, offset)
        offset += 8
        if offset + pcm_len > len(data):
            break
        packets.append((ts_ms, data[offset:offset + pcm_len]))
        offset += pcm_len
    return packets


def _rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0
    samples = array.array('h')
    samples.frombytes(pcm)
    mean_sq = sum(s * s for s in samples) / len(samples)
    return math.sqrt(mean_sq)


def _rms_db(rms: float) -> float:
    if rms <= 0:
        return -999.0
    return 20 * math.log10(rms / 32768.0)


def analyse_session(session_dir: Path) -> dict:
    """Return per-speaker diagnostic stats for a session directory."""
    meta_path = session_dir / 'meta.json'
    user_names: dict[str, str] = {}
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        user_names = {str(uid): name for uid, name in meta.get('user_names', {}).items()}

    speakers = []
    for lsm in sorted(session_dir.glob('*.lsm')):
        uid_str = lsm.stem.split('_')[0]
        name = user_names.get(uid_str, lsm.stem)
        packets = _read_lsm(lsm)
        file_bytes = lsm.stat().st_size

        if not packets:
            speakers.append({
                'uid': uid_str, 'name': name, 'packets': 0,
                'duration_s': 0.0, 'file_kb': round(file_bytes / 1024, 1),
                'rms': 0.0, 'rms_db': -999.0,
            })
            continue

        all_pcm = b''.join(pcm for _, pcm in packets)
        duration_s = len(all_pcm) / (SAMPLE_RATE * 2)  # 16-bit = 2 bytes/sample
        rms = _rms(all_pcm)

        speakers.append({
            'uid': uid_str,
            'name': name,
            'packets': len(packets),
            'duration_s': round(duration_s, 1),
            'file_kb': round(file_bytes / 1024, 1),
            'rms': round(rms, 1),
            'rms_db': round(_rms_db(rms), 1),
        })

    return {'session': session_dir.name, 'speakers': speakers}


def export_wav(session_dir: Path, uid: str, out_path: Path) -> None:
    """Concatenate a speaker's packets in timestamp order and write a WAV."""
    matches = list(session_dir.glob(f'{uid}_*.lsm'))
    if not matches:
        raise FileNotFoundError(f'No .lsm file for uid {uid} in {session_dir}')
    packets = _read_lsm(matches[0])
    packets.sort(key=lambda x: x[0])
    all_pcm = b''.join(pcm for _, pcm in packets)
    with wave.open(str(out_path), 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(all_pcm)


if __name__ == '__main__':
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Diagnose an Orpheus session')
    parser.add_argument('session_dir', help='Path to session directory')
    parser.add_argument('--wav', action='store_true', help='Export WAV files per speaker')
    args = parser.parse_args()

    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f'Error: {session_dir} does not exist', file=sys.stderr)
        sys.exit(1)

    stats = analyse_session(session_dir)
    print(f'\nSession: {stats["session"]}')
    print(f'{"Speaker":<30} {"Packets":>8} {"Duration":>10} {"File KB":>8} {"RMS":>8} {"dBFS":>8}')
    print('-' * 80)
    for s in stats['speakers']:
        print(
            f'{s["name"]:<30} {s["packets"]:>8} '
            f'{s["duration_s"]:>9.1f}s {s["file_kb"]:>7.1f}K '
            f'{s["rms"]:>8.1f} {s["rms_db"]:>7.1f}dB'
        )

    if args.wav:
        print()
        for s in stats['speakers']:
            out = session_dir / f'{s["uid"]}_{s["name"]}.wav'
            try:
                export_wav(session_dir, s['uid'], out)
                print(f'  Exported: {out}')
            except Exception as exc:
                print(f'  Failed ({s["name"]}): {exc}')
