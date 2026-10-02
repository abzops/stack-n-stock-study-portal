"""Transactional local study storage. Never served as static study data."""
import json
import math
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone


class StoreError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def statistics(records):
    values = sorted(float(p['cycleTimeMs']) / 1000 for p in records
                    if isinstance(p.get('cycleTimeMs'), (float, int)) and p['cycleTimeMs'] >= 0)
    n = len(values)
    return {'count': n, 'average': sum(values) / n if n else None,
            'p50': (values[(n-1)//2] + values[n//2]) / 2 if n else None,
            'p90': values[math.ceil(n*.9)-1] if n else None,
            'compliance': 100*sum(v <= 5 for v in values)/n if n else None}


def analyze(snapshot):
    corrections = snapshot.get('corrections', [])
    picks = [dict(p) for p in snapshot.get('picks', [])]
    for p in picks:
        for c in corrections:
            if c.get('pickId') == p.get('id'):
                p.update({k: c[k] for k in ('valid', 'accuracy', 'exception') if k in c})
    valid = [p for p in picks if p.get('valid', True)]
    result = {'overall': statistics(valid), 'slots': [], 'blocks': [], 'alerts': [],
              'accuracy': 'not assessed', 'exceptions': len(snapshot.get('exceptions', [])),
              'invalid': len(picks)-len(valid), 'corrections': len(corrections)}
    assessed = [p for p in picks if p.get('accuracy') in ('correct', 'incorrect')]
    if assessed:
        result['accuracy'] = {'assessed': len(assessed), 'correctPercent': 100*sum(p['accuracy']=='correct' for p in assessed)/len(assessed)}
    for kind, key in [('slots', 'slot'), ('blocks', 'pickBlock')]:
        for group in sorted(set(p.get(key, 1) for p in picks)):
            grouped = [p for p in picks if p.get(key, 1) == group]
            result[kind].append({'label': group, **statistics([p for p in grouped if p.get('valid', True)]),
                                 'errors': sum(p.get('accuracy') == 'incorrect' for p in grouped),
                                 'invalid': sum(not p.get('valid', True) for p in grouped)})
    if len(valid) >= 20:
        recent = statistics(valid[-20:])
        if recent['p90'] > 5:
            result['alerts'].append(f"Recent P90 is {recent['p90']:.2f}s across 20 valid picks (target 5s). Review slow slots and recorded delays.")
        if len(valid) >= 40:
            base = statistics(valid[:20])['p50']
            if base and recent['p50'] > base * 1.2:
                result['alerts'].append(f"Recent median is {recent['p50']:.2f}s versus the first 20-pick baseline of {base:.2f}s, over 20% slower. Review conditions and ask the operator before changing the protocol.")
    for tote_id, tote in snapshot.get('inventory', {}).get('totes', {}).items():
        if any(s.get('physicalQty') != s.get('digitalQty') for s in tote.get('slots', [])):
            result['alerts'].append(f'Tote {tote_id}: physical and portal quantities differ. Pause and verify the count.')
    return result


class StudyStore:
    def __init__(self, path):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, revision INTEGER NOT NULL,
                updated TEXT NOT NULL, snapshot TEXT NOT NULL, owner TEXT, lease REAL DEFAULT 0);
              CREATE TABLE IF NOT EXISTS events(session_id TEXT, id TEXT, body TEXT NOT NULL,
                PRIMARY KEY(session_id,id));
              CREATE TABLE IF NOT EXISTS receipts(session_id TEXT, request_id TEXT, body TEXT NOT NULL,
                PRIMARY KEY(session_id,request_id));
              CREATE TABLE IF NOT EXISTS presets(id TEXT PRIMARY KEY, name TEXT NOT NULL, config TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, session_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
            if not row:
                raise StoreError('Session not found', 404)
            return {'id': row['id'], 'revision': row['revision'], 'updated': row['updated'],
                    'snapshot': json.loads(row['snapshot'])}

    def list(self):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM sessions ORDER BY updated DESC').fetchall()
        return [{'id': r['id'], 'revision': r['revision'], 'updated': r['updated'],
                 'metadata': json.loads(r['snapshot'])['metadata'],
                 'state': json.loads(r['snapshot'])['machine']['currentState'],
                 'picks': len(json.loads(r['snapshot']).get('picks', []))} for r in rows]

    def claim(self, session_id, writer):
        if not isinstance(writer, str) or not writer:
            raise StoreError('Writer ID is required')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM sessions WHERE id=?', (session_id,)).fetchone()
            if not row:
                raise StoreError('Session not found', 404)
            if row['owner'] != writer and row['lease'] > time.time():
                raise StoreError('This session is open in another tab. Close it and retry after 8 seconds.', 409)
            db.execute('UPDATE sessions SET owner=?,lease=? WHERE id=?', (writer,time.time()+8,session_id))
        return self.get(session_id)

    @staticmethod
    def validate(snapshot):
        if not isinstance(snapshot, dict) or not all(k in snapshot for k in ('metadata','machine','inventory','picks','events')):
            raise StoreError('Incomplete session snapshot')
        meta = snapshot['metadata']
        protocol = meta.get('protocol', {})
        if not meta.get('studyId') or not meta.get('operator') or meta.get('numSlots') not in (4,6):
            raise StoreError('Invalid study configuration')
        for key in ('durationSec','workSec','breakSec','maxCycles'):
            value = protocol.get(key)
            if not isinstance(value,int) or isinstance(value,bool) or not 1 <= value <= (10000 if key=='maxCycles' else 86400):
                raise StoreError('Protocol values must be positive whole numbers within limits')
        if protocol.get('completion') not in ('time','cycles','either') or meta.get('mode') not in ('MODE_A','MODE_B'):
            raise StoreError('Invalid completion rule or mode')
        for event in snapshot['events']:
            if not isinstance(event.get('id'),str) or not event['id']:
                raise StoreError('Every event needs a stable ID')
        for key in ('picks','events','corrections','exceptions'):
            items = snapshot.get(key, [])
            if not isinstance(items, list) or any(not isinstance(item, dict) or not item.get('id') for item in items):
                raise StoreError(f'Every {key} record needs an ID')
            if len({item['id'] for item in items}) != len(items):
                raise StoreError(f'Duplicate IDs in {key}')
        for item in snapshot.get('corrections', []) + snapshot.get('exceptions', []):
            if not str(item.get('reason', '')).strip():
                raise StoreError('Corrections and exceptions need a reason')

    def save(self, session_id, payload):
        snapshot = payload.get('snapshot')
        self.validate(snapshot)
        writer, request = payload.get('writer'), payload.get('requestId')
        if not writer or not request or not isinstance(payload.get('revision'),int):
            raise StoreError('Writer, request ID and revision are required')
        encoded = json.dumps(snapshot, sort_keys=True, allow_nan=False)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            receipt = db.execute('SELECT body FROM receipts WHERE session_id=? AND request_id=?',(session_id,request)).fetchone()
            if receipt:
                return json.loads(receipt['body'])
            row = db.execute('SELECT * FROM sessions WHERE id=?',(session_id,)).fetchone()
            if row:
                if row['revision'] != payload['revision'] or row['owner'] != writer:
                    raise StoreError('Session changed in another tab. Reopen the saved session; your pending copy is retained.',409)
                old = json.loads(row['snapshot'])
                if old['metadata'] != snapshot['metadata']:
                    raise StoreError('Locked session configuration cannot be changed',409)
                for key in ('picks','corrections','exceptions'):
                    before = old.get(key,[])
                    if snapshot.get(key,[])[:len(before)] != before:
                        raise StoreError(f'Original {key} cannot be overwritten; append a correction',409)
                old_events = {event['id'] for event in old['events']}
                if not old_events.issubset({event['id'] for event in snapshot['events']}):
                    raise StoreError('Original events cannot be removed',409)
                if old['machine']['currentState']=='COMPLETED' and snapshot['machine']['currentState']!='COMPLETED':
                    raise StoreError('Completed studies cannot be resumed',409)
            elif payload['revision'] != 0:
                raise StoreError('Session revision does not exist',409)
            for event in snapshot['events']:
                body = json.dumps(event, sort_keys=True)
                prior = db.execute('SELECT body FROM events WHERE session_id=? AND id=?',(session_id,event['id'])).fetchone()
                if prior and prior['body'] != body:
                    raise StoreError('Original events cannot be changed',409)
                db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(session_id,event['id'],body))
            revision = payload['revision']+1
            updated = utcnow()
            db.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?,?,?)',(session_id,revision,updated,encoded,writer,time.time()+8))
            result = {'revision':revision,'updated':updated,'id':session_id}
            db.execute('INSERT INTO receipts VALUES(?,?,?)',(session_id,request,json.dumps(result)))
            return result

    def presets(self, payload=None):
        with self.connect() as db:
            if payload is not None:
                if not payload.get('id') or not str(payload.get('name','')).strip() or not isinstance(payload.get('config'),dict):
                    raise StoreError('Preset ID, name and configuration are required')
                db.execute('INSERT OR REPLACE INTO presets VALUES(?,?,?)',(payload['id'],payload['name'].strip(),json.dumps(payload['config'])))
            return [dict(r, config=json.loads(r['config'])) for r in db.execute('SELECT * FROM presets ORDER BY name')]
