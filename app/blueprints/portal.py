"""Public-facing portal — hub homepage and campaign landing pages."""
from flask import Blueprint, abort, render_template
from app.auth import is_staff
from app.db import Campaign, CAMPAIGN_STATUS_LABELS

bp = Blueprint('portal', __name__)


@bp.route('/')
def index():
    campaigns = Campaign.query.order_by(Campaign.sort_order, Campaign.name).all()
    if not is_staff():
        campaigns = [c for c in campaigns if c.status != 'draft']
    # Group by status for display ordering: active first, then upcoming, hiatus, complete
    order = {'active': 0, 'upcoming': 1, 'hiatus': 2, 'complete': 3, 'draft': 4}
    campaigns = sorted(campaigns, key=lambda c: (order.get(c.status, 9), c.sort_order))
    return render_template('portal/index.html',
                           campaigns=campaigns,
                           status_labels=CAMPAIGN_STATUS_LABELS)


@bp.route('/<campaign_slug>/')
def campaign_home(campaign_slug):
    c = Campaign.query.filter_by(slug=campaign_slug).first_or_404()
    if c.status == 'draft' and not is_staff():
        abort(404)
    return render_template('portal/campaign.html', campaign=c,
                           status_labels=CAMPAIGN_STATUS_LABELS)
