"""Player-known, local Rin route schematic for the S&V starter."""
import json
from pathlib import Path

from datetime import datetime
from flask import Blueprint, abort, jsonify, render_template, request
from sqlalchemy.exc import IntegrityError
from app.auth import is_staff
from app.db import Campaign, SectorSnapshot, db
from app.sector_state import geography, validate_snapshot

bp = Blueprint('sav', __name__, url_prefix='/sav')
SITES = Path(__file__).resolve().parents[1] / 'static/sav/sites.json'


def public_campaign():
    campaign = Campaign.query.filter_by(slug='sav').first_or_404()
    if campaign.status == 'draft' and not is_staff():
        abort(404)
    return campaign


@bp.get('/atlas/')
def atlas():
    campaign = public_campaign()
    return render_template('sav/atlas.html', campaign=campaign,
                           sites=json.loads(SITES.read_text()))


@bp.get('/atlas/sector/')
def sector():
    return render_template('sav/sector.html', campaign=public_campaign())


def snapshot_response(row):
    return dict(revision=row.revision if row else 0,
                state=json.loads(row.state_json) if row else geography()['defaultState'],
                updatedAt=row.updated_at.isoformat() + 'Z' if row else None)


@bp.route('/atlas/sector/state', methods=['GET', 'PUT'])
def sector_state():
    campaign = public_campaign()
    if request.method == 'GET':
        response = jsonify(snapshot_response(db.session.get(SectorSnapshot, campaign.id)))
        response.headers['Cache-Control'] = 'no-store'
        return response
    if not is_staff():
        return jsonify(error='Staff sign-in is required to publish a sector snapshot.'), 403
    if request.content_length is None or request.content_length > 200000:
        return jsonify(error='Snapshot must be smaller than 200 KB.'), 413
    payload = request.get_json(silent=True)
    try:
        if not isinstance(payload, dict) or set(payload) != {'revision', 'state'}:
            raise ValueError('Expected revision and state.')
        revision = payload['revision']
        if type(revision) is not int or revision < 0:
            raise ValueError('Invalid revision.')
        state = validate_snapshot(payload['state'])
    except (ValueError, TypeError, KeyError) as error:
        return jsonify(error=str(error)), 400
    row = db.session.get(SectorSnapshot, campaign.id)
    if row is None:
        if revision != 0:
            return jsonify(error='Snapshot changed. Reload before publishing.'), 409
        row = SectorSnapshot(campaign_id=campaign.id, revision=1,
                             state_json=json.dumps(state), updated_at=datetime.utcnow())
        db.session.add(row)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify(error='Snapshot changed. Reload before publishing.'), 409
    else:
        updated = db.session.query(SectorSnapshot).filter_by(
            campaign_id=campaign.id, revision=revision).update(
                dict(state_json=json.dumps(state), revision=revision + 1,
                     updated_at=datetime.utcnow()), synchronize_session=False)
        if not updated:
            db.session.rollback()
            return jsonify(error='Snapshot changed. Reload before publishing.'), 409
        db.session.commit()
        db.session.expire_all()
        row = db.session.get(SectorSnapshot, campaign.id)
    return jsonify(snapshot_response(row))
