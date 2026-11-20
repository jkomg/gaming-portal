"""Validate and whitelist the public Procyon snapshot; never accept GM-only documents."""
import json
from pathlib import Path

GEOGRAPHY = Path(__file__).parent / 'static/sav/sector/sector.json'


def geography():
    return json.loads(GEOGRAPHY.read_text())


def validate_snapshot(state):
    geo = geography()
    if not isinstance(state, dict) or type(state.get('version')) is not int or state.get('version') != 1:
        raise ValueError('Expected a Procyon sector version 1 snapshot.')
    fields = {'version', 'systems', 'factionState', 'presence', 'markers', 'routes', 'ship'}
    if set(state) != fields:
        raise ValueError('Snapshot contains unexpected or missing fields.')

    def record(value, keys):
        if not isinstance(value, dict) or set(value) != set(keys):
            raise ValueError('Invalid snapshot record.')

    def number(value, low, high):
        if type(value) is not int or not low <= value <= high:
            raise ValueError('Invalid numeric value.')

    def text(value, size=500):
        if not isinstance(value, str) or len(value) > size:
            raise ValueError('Invalid text value.')

    system_ids = {s['id'] for s in geo['systems']}
    record(state['systems'], system_ids)
    for value in state['systems'].values():
        record(value, ('heat', 'wanted', 'notes'))
        number(value['heat'], 0, 8)
        number(value['wanted'], 0, 4)
        text(value['notes'])
    record(state['factionState'], geo['factions'])
    for value in state['factionState'].values():
        record(value, ('status',))
        number(value['status'], -3, 3)
    known = {location['id'] for location in geo['locations']}
    markers = state['markers']
    if not isinstance(markers, list) or len(markers) > 100:
        raise ValueError('Too many custom locations.')
    for marker in markers:
        record(marker, ('id', 'name', 'system', 'x', 'y', 'kind', 'summary'))
        text(marker['id'], 80)
        if not marker['id'] or not all(c in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in marker['id']):
            raise ValueError('Invalid custom location identifier.')
        if marker['id'] in known or marker['system'] not in system_ids:
            raise ValueError('Invalid or duplicate custom location.')
        known.add(marker['id'])
        text(marker['name'], 80)
        if not marker['name'].strip():
            raise ValueError('Location name is required.')
        text(marker['kind'], 80)
        text(marker['summary'])
        number(marker['x'], 0, 1800)
        number(marker['y'], 0, 1150)
    presence = state['presence']
    if not isinstance(presence, list) or len(presence) > 300:
        raise ValueError('Too much faction presence.')
    seen = set()
    for p in presence:
        record(p, ('location', 'faction', 'strength', 'note'))
        text(p['location'], 80)
        text(p['faction'], 100)
        if p['location'] not in known or p['faction'] not in geo['factions']:
            raise ValueError('Unknown location or faction.')
        if p['strength'] not in ('HQ', 'Presence', 'Contested'):
            raise ValueError('Unknown faction foothold type.')
        text(p['note'])
        pair = (p['location'], p['faction'])
        if pair in seen:
            raise ValueError('Duplicate faction presence.')
        seen.add(pair)
    record(state['routes'], (r['id'] for r in geo['routes']))
    for r in state['routes'].values():
        record(r, ('status', 'notes'))
        if r['status'] not in ('open', 'watched', 'blocked', 'sealed'):
            raise ValueError('Invalid route status.')
        text(r['notes'])
    record(state['ship'], ('location',))
    text(state['ship']['location'], 80)
    if state['ship']['location'] not in known:
        raise ValueError('Unknown ship location.')
    return state
