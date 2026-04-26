"""Discord OAuth2 login / logout."""
import secrets
import requests as http
from flask import (
    Blueprint, redirect, url_for, session, flash, request, render_template,
    current_app,
)
from app.auth import pop_login_next

bp = Blueprint('auth', __name__)

DISCORD_AUTH_URL  = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'
DISCORD_USER_URL  = 'https://discord.com/api/v10/users/@me'


@bp.route('/login')
def login():
    if session.get('authenticated'):
        return redirect(url_for('admin.index'))
    # Stash ?next= if provided
    next_path = request.args.get('next', '').strip()
    if next_path and next_path.startswith('/') and not next_path.startswith('//'):
        session['login_next'] = next_path
    return render_template('login.html')


@bp.route('/auth/discord')
def discord_redirect():
    next_path = request.args.get('next', '').strip()
    if next_path and next_path.startswith('/') and not next_path.startswith('//'):
        session['login_next'] = next_path
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    params = {
        'client_id': current_app.config['DISCORD_CLIENT_ID'],
        'redirect_uri': current_app.config['DISCORD_REDIRECT_URI'],
        'response_type': 'code',
        'scope': 'identify',
        'state': state,
    }
    qs = '&'.join(f'{k}={http.utils.quote(str(v))}' for k, v in params.items())
    return redirect(f'{DISCORD_AUTH_URL}?{qs}')


@bp.route('/auth/callback')
def discord_callback():
    state = request.args.get('state')
    if not state or state != session.pop('oauth_state', None):
        flash('Invalid OAuth state. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    error = request.args.get('error')
    if error:
        flash(f'Discord login failed: {error}', 'danger')
        return redirect(url_for('auth.login'))

    code = request.args.get('code')
    if not code:
        flash('No authorization code received.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        token_resp = http.post(DISCORD_TOKEN_URL, data={
            'client_id': current_app.config['DISCORD_CLIENT_ID'],
            'client_secret': current_app.config['DISCORD_CLIENT_SECRET'],
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': current_app.config['DISCORD_REDIRECT_URI'],
        }, headers={'Content-Type': 'application/x-www-form-urlencoded'}, timeout=10)
        token_resp.raise_for_status()
        access_token = token_resp.json().get('access_token')
    except Exception as exc:
        current_app.logger.error('Discord token exchange failed: %s', exc)
        flash('Failed to authenticate with Discord. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        user_resp = http.get(DISCORD_USER_URL,
                             headers={'Authorization': f'Bearer {access_token}'},
                             timeout=10)
        user_resp.raise_for_status()
        user_data = user_resp.json()
    except Exception:
        flash('Failed to fetch Discord user info.', 'danger')
        return redirect(url_for('auth.login'))

    discord_id   = str(user_data.get('id', ''))
    discord_name = user_data.get('global_name') or user_data.get('username', 'Unknown')
    next_url     = pop_login_next(url_for('portal.index'))

    session.clear()
    session['discord_id']   = discord_id
    session['discord_name'] = discord_name
    session.permanent = True

    if discord_id in current_app.config.get('ALLOWED_DISCORD_IDS', set()):
        session['authenticated'] = True
        session['staff_user']    = discord_name
        flash(f'Welcome, {discord_name}.', 'success')
        return redirect(next_url if next_url != url_for('portal.index')
                        else url_for('admin.index'))

    flash('Your Discord account is not authorised as staff.', 'warning')
    return redirect(url_for('portal.index'))


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('portal.index'))
