from __future__ import annotations
import os
from flask import Flask
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from .db import db

migrate = Migrate()
csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')

    # Config
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

    _db_url = os.environ.get('DATABASE_URL', '')
    _turso_connect_url = None
    _turso_token = None

    if not _db_url:
        # Local dev: SQLite
        _data_dir = os.path.abspath(os.path.join(app.root_path, '..', 'data'))
        os.makedirs(_data_dir, exist_ok=True)
        _db_url = f'sqlite:///{_data_dir}/db.sqlite'
    elif _db_url.startswith('libsql://'):
        # Turso: use HTTP adapter via creator; SQLAlchemy URI is a dummy
        _turso_token = os.environ.get('TURSO_AUTH_TOKEN', '')
        _turso_connect_url = 'https://' + _db_url[len('libsql://'):]
        _db_url = 'sqlite://'

    app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    if _turso_connect_url:
        from .turso_http import connect as _turso_connect
        from sqlalchemy.pool import NullPool
        _t_url, _t_token = _turso_connect_url, _turso_token

        def _turso_creator():
            return _turso_connect(_t_url, auth_token=_t_token)

        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'creator': _turso_creator, 'poolclass': NullPool}
    app.config['WTF_CSRF_TIME_LIMIT'] = None

    app.config['DISCORD_CLIENT_ID'] = os.environ.get('DISCORD_CLIENT_ID', '')
    app.config['DISCORD_CLIENT_SECRET'] = os.environ.get('DISCORD_CLIENT_SECRET', '')
    app.config['DISCORD_REDIRECT_URI'] = os.environ.get('DISCORD_REDIRECT_URI', 'http://localhost:8080/auth/callback')
    app.config['ALLOWED_DISCORD_IDS'] = set(
        x.strip() for x in os.environ.get('ALLOWED_DISCORD_IDS', '').split(',') if x.strip()
    )

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Blueprints
    from .blueprints.portal import bp as portal_bp
    from .blueprints.admin import bp as admin_bp
    from .blueprints.wiki import bp as wiki_bp
    from .blueprints.auth_bp import bp as auth_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(portal_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(wiki_bp, url_prefix='/<campaign_slug>/wiki')

    # Global template context
    from .auth import is_staff as _is_staff, is_logged_in as _is_logged_in
    from flask import session

    @app.context_processor
    def _globals():
        return {
            'is_staff': _is_staff(),
            'is_logged_in': _is_logged_in(),
            'session': session,
        }

    # Create tables on first run
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass  # already exists — safe to ignore
        _seed_campaigns_if_empty()

    return app


def _seed_campaigns_if_empty():
    """Seed the four known campaigns on first boot so the homepage isn't blank."""
    from .db import Campaign
    import json
    if Campaign.query.count() > 0:
        return

    campaigns = [
        Campaign(
            slug='mcbn',
            name='Music City by Night',
            system='Vampire: the Masquerade V5',
            status='active',
            description='The Kindred of Nashville navigate politics, power, and the ancient darkness beneath the city.',
            cover_image_url='/static/img/mcbn.png',
            wiki_url='https://mcbn.jkomg.us/wiki',
            sort_order=1,
        ),
        Campaign(
            slug='gotw',
            name='Ghosts of the Wayline',
            system='Scum & Villainy',
            status='active',
            description='A mysterious Precursor signal bleeds through the Procyon Sector. Multiple factions want it. Your crew just wanted a simple job.',
            cover_image_url='/static/img/gotw.png',
            sort_order=2,
            _notion_databases=json.dumps({
                'characters': 'c2d7cdd8-5938-4ee2-9986-02580d84f2ac',
                'locations':  '9007ee36-f931-4298-9986-b82c7b6e2a53',
                'factions':   '63c814ca-8ad1-437b-99f0-f10a44819820',
                'lore':       '2b44db63-34bb-4800-b7fa-7c7c5352d9af',
            }),
        ),
        Campaign(
            slug='vecna',
            name='Vecna: Eve of Ruin',
            system='Dungeons & Dragons 5e',
            status='active',
            description='The lich-god Vecna prepares the Ritual of Remaking. Only one crew can stop him before the multiverse is unmade.',
            cover_image_url='/static/img/vecna.png',
            sort_order=3,
            _notion_databases=json.dumps({
                'lore':       '3483a3e5-cab1-8102-b08c-db68df72deab',
                'characters': '3483a3e5-cab1-8157-aa2d-e0f26e067598',
                'factions':   '3483a3e5-cab1-81a2-a4bf-c05bdb1f35b6',
                'locations':  '3483a3e5-cab1-81a9-96ad-f0a09824205e',
            }),
        ),
        Campaign(
            slug='keys',
            name='Keys from the Golden Vault',
            system='Dungeons & Dragons 5e',
            status='active',
            description='Thirteen daring heists, each a self-contained caper. The Golden Vault calls — will you answer?',
            cover_image_url='/static/img/keys.png',
            sort_order=4,
            _notion_databases=json.dumps({
                'lore':       '3483a3e5-cab1-81e8-a61d-c540cbe7cd26',
                'characters': '3483a3e5-cab1-81ac-b84f-e62686a85b51',
                'factions':   '3483a3e5-cab1-817a-a15a-ffc8223aa1bf',
                'locations':  '3483a3e5-cab1-8164-b7b6-f6ada0060ee2',
            }),
        ),
    ]
    for c in campaigns:
        db.session.add(c)
    db.session.commit()
