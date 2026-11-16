"""Player-known, local Rin route schematic for the S&V starter."""
import json
from pathlib import Path

from flask import Blueprint, abort, render_template
from app.auth import is_staff
from app.db import Campaign

bp = Blueprint('sav', __name__, url_prefix='/sav')
SITES = Path(__file__).resolve().parents[1] / 'static/sav/sites.json'


@bp.get('/atlas/')
def atlas():
    campaign = Campaign.query.filter_by(slug='sav').first_or_404()
    if campaign.status == 'draft' and not is_staff():
        abort(404)
    return render_template('sav/atlas.html', campaign=campaign,
                           sites=json.loads(SITES.read_text()))
