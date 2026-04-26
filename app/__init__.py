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
    if not _db_url or _db_url == 'sqlite:///data/db.sqlite':
        _data_dir = os.path.abspath(os.path.join(app.root_path, '..', 'data'))
        os.makedirs(_data_dir, exist_ok=True)
        _db_url = f'sqlite:///{_data_dir}/db.sqlite'
    app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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
        db.create_all()
        _seed_campaigns_if_empty()

    return app


def _seed_campaigns_if_empty():
    """Seed the four known campaigns on first boot so the homepage isn't blank."""
    from .db import Campaign
    if Campaign.query.count() > 0:
        return
    import json
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
        ),
        Campaign(
            slug='vecna',
            name='Vecna: Eve of Ruin',
            system='Dungeons & Dragons 5e',
            status='active',
            description='The lich-god Vecna prepares the Ritual of Remaking. Only one crew can stop him before the multiverse is unmade.',
            cover_image_url='/static/img/vecna.png',
            sort_order=3,
        ),
        Campaign(
            slug='keys',
            name='Keys from the Golden Vault',
            system='Dungeons & Dragons 5e',
            status='active',
            description='Thirteen daring heists, each a self-contained caper. The Golden Vault calls — will you answer?',
            cover_image_url='/static/img/keys.png',
            sort_order=4,
        ),
    ]
    for c in campaigns:
        db.session.add(c)
    db.session.commit()
