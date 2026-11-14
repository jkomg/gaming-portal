"""Read-only, player-known Crow's Foot atlas for the Blades campaign."""
from flask import Blueprint, abort, render_template
from app.auth import is_staff
from app.db import Campaign

bp = Blueprint('blades', __name__, url_prefix='/blades')


@bp.get('/atlas/')
def atlas():
    campaign = Campaign.query.filter_by(slug='blades').first_or_404()
    if campaign.status == 'draft' and not is_staff():
        abort(404)
    return render_template('blades/atlas.html', campaign=campaign)
