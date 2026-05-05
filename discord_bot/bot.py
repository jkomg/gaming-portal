"""Orpheus — TTRPG session recording bot.

Slash commands:
  /record start campaign:<slug>  — join voice and start recording
  /record stop                   — stop, transcribe, summarize, post to wiki
  /record status                 — show elapsed time and captured speakers
  /record campaigns              — list available campaign slugs
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, voice_recv
from dotenv import load_dotenv

from status_api import LogBufferHandler

# ── Patch discord-ext-voice-recv to skip corrupted Opus packets ───────────────
# The alpha library crashes its router thread on bad packets; we make it return
# None instead so the router loop continues normally.
def _patch_voice_recv() -> None:
    try:
        from discord.ext.voice_recv import opus as _vr_opus
        import discord.opus as _opus

        _orig = _vr_opus.PacketDecoder.pop_data

        def _safe_pop_data(self):
            try:
                return _orig(self)
            except _opus.OpusError:
                return None

        _vr_opus.PacketDecoder.pop_data = _safe_pop_data
    except Exception:
        pass  # if the internals change, don't block startup

_patch_voice_recv()

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────

_fmt = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s: %(message)s')
_stream = logging.StreamHandler()
_stream.setFormatter(_fmt)
_buffer = LogBufferHandler()
_buffer.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_stream, _buffer])
log = logging.getLogger('orpheus')

# ── Config ────────────────────────────────────────────────────────────────────

DISCORD_TOKEN = os.environ['DISCORD_BOT_TOKEN']
GUILD_IDS = [
    int(x.strip())
    for x in os.environ.get('DISCORD_GUILD_IDS', '').split(',')
    if x.strip()
]
STATUS_PORT = int(os.environ.get('STATUS_PORT', 8765))

# ── Bot ───────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# guild_id -> recording state dict
_active: dict[int, dict] = {}

# Current post-processing progress — mutated in-place so status_api sees live updates
_processing: dict = {}

# ── Slash commands ────────────────────────────────────────────────────────────

record_group = app_commands.Group(name='record', description='Session recording')
bot.tree.add_command(record_group)


@record_group.command(name='start', description='Start recording the current voice channel')
@app_commands.describe(campaign='Campaign slug (e.g. vecna, gotw, keys)')
async def record_start(interaction: discord.Interaction, campaign: str) -> None:
    await interaction.response.defer(ephemeral=True)

    gid = interaction.guild_id
    if gid in _active:
        await interaction.followup.send('Already recording — use `/record stop` first.', ephemeral=True)
        return

    if not (interaction.user.voice and interaction.user.voice.channel):
        await interaction.followup.send('You need to be in a voice channel first.', ephemeral=True)
        return

    campaign = campaign.lower().strip()
    from wiki_poster import get_campaign_id
    campaign_id = get_campaign_id(campaign)
    if campaign_id is None:
        await interaction.followup.send(
            f'Campaign `{campaign}` not found. Use `/record campaigns` to see valid slugs.',
            ephemeral=True,
        )
        return

    from audio_sink import SessionSink
    started_at = datetime.utcnow()
    session_id = f'{started_at.strftime("%Y%m%d_%H%M")}_{campaign}'
    sink = SessionSink(session_id)
    channel = interaction.user.voice.channel
    vc: voice_recv.VoiceRecvClient = await channel.connect(cls=voice_recv.VoiceRecvClient)
    vc.listen(sink)

    _active[gid] = {
        'vc': vc,
        'sink': sink,
        'campaign': campaign,
        'campaign_id': campaign_id,
        'started_at': started_at,
        'session_id': session_id,
        'notify_channel_id': interaction.channel_id,
    }
    log.info('Recording started: campaign=%s channel=%s', campaign, channel.name)

    await interaction.followup.send(
        f'Recording **{channel.name}** for **{campaign}**.\nUse `/record stop` when done.',
        ephemeral=True,
    )


@record_group.command(name='stop', description='Stop recording and post notes to the wiki')
async def record_stop(interaction: discord.Interaction) -> None:
    await interaction.response.defer(ephemeral=True)

    gid = interaction.guild_id
    if gid not in _active:
        await interaction.followup.send('No active recording.', ephemeral=True)
        return

    state = _active.pop(gid)
    vc: voice_recv.VoiceRecvClient = state['vc']
    sink = state['sink']

    vc.stop_listening()
    await vc.disconnect()
    sink.save_meta(state['campaign'], state['campaign_id'],
                   state['started_at'].isoformat())
    sink.cleanup()

    elapsed_ms = sink.session_duration_ms()
    h, rem = divmod(elapsed_ms // 1000, 3600)
    m, s = divmod(rem, 60)
    speakers = list(sink.user_names.values())
    log.info('Recording stopped: %02d:%02d:%02d, speakers=%s', h, m, s, speakers)

    await interaction.followup.send(
        f'Recording stopped ({h:02d}:{m:02d}:{s:02d}, '
        f'speakers: {", ".join(speakers) or "none"}).\n'
        'Transcribing — I\'ll post here when notes are ready.',
        ephemeral=False,
    )

    asyncio.create_task(_process(state, sink, elapsed_ms, interaction.channel_id))


@record_group.command(name='status', description='Show current recording status')
async def record_status(interaction: discord.Interaction) -> None:
    gid = interaction.guild_id
    if gid not in _active:
        await interaction.response.send_message('No active recording.', ephemeral=True)
        return

    state = _active[gid]
    sink = state['sink']
    elapsed_ms = sink.session_duration_ms()
    h, rem = divmod(elapsed_ms // 1000, 3600)
    m, s = divmod(rem, 60)
    speakers = list(sink.user_names.values())

    await interaction.response.send_message(
        f'Recording **{state["campaign"]}** — {h:02d}:{m:02d}:{s:02d} elapsed\n'
        f'Speakers: {", ".join(speakers) or "none yet"}',
        ephemeral=True,
    )


@record_group.command(name='reprocess', description='Reprocess a saved session from disk')
@app_commands.describe(session_id='Session folder name (e.g. 20250428_2100_keys)')
async def record_reprocess(interaction: discord.Interaction, session_id: str) -> None:
    await interaction.response.defer(ephemeral=True)
    ok = await _reprocess_session(session_id.strip(), interaction.channel_id)
    if not ok:
        await interaction.followup.send(
            f'Session `{session_id}` not found or has no audio files.',
            ephemeral=True,
        )
        return
    await interaction.followup.send(
        f'Reprocessing `{session_id}` — I\'ll post here when notes are ready.',
        ephemeral=False,
    )


@record_reprocess.autocomplete('session_id')
async def _reprocess_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    from audio_sink import SESSIONS_DIR
    if not SESSIONS_DIR.exists():
        return []
    dirs = [
        d.name for d in sorted(SESSIONS_DIR.iterdir(), reverse=True)
        if d.is_dir() and list(d.glob('*.lsm'))
    ]
    return [
        app_commands.Choice(name=d, value=d)
        for d in dirs if current.lower() in d.lower()
    ][:25]


@record_group.command(name='campaigns', description='List available campaign slugs')
async def record_campaigns(interaction: discord.Interaction) -> None:
    from wiki_poster import get_campaigns
    camps = get_campaigns()
    lines = [f'`{c["slug"]}` — {c["name"]}' for c in camps]
    await interaction.response.send_message('\n'.join(lines) or 'No campaigns found.', ephemeral=True)


@record_start.autocomplete('campaign')
async def _campaign_autocomplete(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    from wiki_poster import get_campaigns
    camps = get_campaigns()
    return [
        app_commands.Choice(name=c['name'], value=c['slug'])
        for c in camps
        if current.lower() in c['slug'] or current.lower() in c['name'].lower()
    ][:25]


# ── Processing pipeline ───────────────────────────────────────────────────────

async def _process(state: dict, sink, duration_ms: int, channel_id: int) -> None:
    global _processing
    channel = bot.get_channel(channel_id)
    try:
        from audio_sink import load_session
        chunks, user_names = load_session(sink.session_dir)

        if not chunks:
            if channel:
                await channel.send('No audio captured — session notes skipped.')
            return

        total_users = len(chunks)
        processing_started_at = datetime.utcnow().isoformat() + 'Z'

        def set_progress(**kwargs) -> None:
            _processing.clear()
            _processing['started_at'] = processing_started_at
            _processing.update(kwargs)

        def on_transcription_progress(completed: int, name: str) -> None:
            set_progress(phase='transcribing', detail=f'Transcribing {name}…',
                         current=completed, total=total_users)

        set_progress(phase='transcribing', detail='Starting transcription…',
                     current=0, total=total_users)
        log.info('Transcribing %d users...', total_users)
        transcript_lines = await asyncio.to_thread(
            _run_transcription, chunks, user_names, duration_ms, on_transcription_progress
        )

        if not transcript_lines:
            _processing.clear()
            if channel:
                await channel.send('Transcription returned no text — notes not posted.')
            return

        set_progress(phase='summarizing', detail='Claude is reading the transcript…',
                     current=1, total=1)
        log.info('Summarizing %d transcript lines...', len(transcript_lines))
        summary_md = await asyncio.to_thread(
            _run_summarize,
            transcript_lines,
            state['campaign'],
            state['started_at'].strftime('%B %-d, %Y'),
        )

        set_progress(phase='posting', detail='Writing session to wiki…', current=1, total=1)
        log.info('Posting session to wiki...')
        wiki_url = await asyncio.to_thread(
            _run_post,
            state['campaign_id'],
            state['campaign'],
            state['started_at'],
            summary_md,
            transcript_lines,
        )

        _processing.clear()
        log.info('Session posted: %s', wiki_url)
        # Clean up raw audio now that it's safely in the wiki
        # Set KEEP_SESSIONS=1 in .env to skip deletion for diagnostic purposes
        if not os.environ.get('KEEP_SESSIONS'):
            import shutil
            shutil.rmtree(sink.session_dir, ignore_errors=True)
        if channel:
            await channel.send(f'Session notes posted: {wiki_url}')

    except Exception as exc:
        _processing.clear()
        log.exception('Error processing session')
        if channel:
            await channel.send(f'Error generating session notes: {exc}')


def _run_transcription(chunks, user_names, duration_ms, progress_callback=None):
    from transcribe import transcribe_wavs
    return transcribe_wavs(chunks, user_names, duration_ms, progress_callback)


def _run_summarize(transcript_lines, campaign, date_str):
    from summarize import summarize_transcript
    return summarize_transcript(transcript_lines, campaign, date_str)


async def _reprocess_session(session_id: str, channel_id: int = 0) -> bool:
    """Load a saved session from disk and run the full processing pipeline."""
    import json as _json
    from audio_sink import SESSIONS_DIR

    session_dir = SESSIONS_DIR / session_id
    meta_path = session_dir / 'meta.json'
    if not session_dir.exists() or not meta_path.exists():
        return False
    if not list(session_dir.glob('*.lsm')):
        return False

    meta = _json.loads(meta_path.read_text())

    class _Sink:
        pass

    sink = _Sink()
    sink.session_dir = session_dir  # type: ignore[attr-defined]

    state = {
        'campaign': meta['campaign'],
        'campaign_id': meta['campaign_id'],
        'started_at': datetime.fromisoformat(meta['started_at']),
        'session_id': session_id,
    }
    log.info('Reprocessing session %s', session_id)
    asyncio.create_task(_process(state, sink, 0, channel_id))
    return True


async def _sync_commands() -> None:
    for guild_id in GUILD_IDS:
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        log.info('Commands synced to guild %d (via API)', guild_id)
    if not GUILD_IDS:
        await bot.tree.sync()
        log.info('Commands synced globally (via API)')


def _run_post(campaign_id, campaign, started_at, summary_md, transcript_lines):
    from wiki_poster import post_session
    return post_session(campaign_id, campaign, started_at, summary_md, transcript_lines)


# ── Events ────────────────────────────────────────────────────────────────────

_status_started = False

@bot.event
async def on_ready() -> None:
    global _status_started
    log.info('Orpheus online as %s (id=%s)', bot.user, bot.user.id)

    if not _status_started:
        _status_started = True
        from status_api import start
        from audio_sink import SESSIONS_DIR
        asyncio.create_task(start(
            _active, _processing, port=STATUS_PORT,
            reprocess_fn=_reprocess_session,
            sync_fn=_sync_commands,
            sessions_dir=SESSIONS_DIR,
        ))

    for guild_id in GUILD_IDS:
        guild = discord.Object(id=guild_id)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
        log.info('Commands synced to guild %d', guild_id)

    if not GUILD_IDS:
        await bot.tree.sync()
        log.info('Commands synced globally')


if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
