"""Workspace cache; authenticated entries never share the public namespace."""
from __future__ import annotations

import json
from dataclasses import asdict

from .storage import SQLiteRepository, utc_now


class CompanionStore(SQLiteRepository):
    def cached(self, kind, key='', account=''):
        with self._connect() as db:
            row = db.execute('SELECT payload, updated_at FROM companion_cache WHERE account=? AND kind=? AND key=?',
                             (account, kind, key)).fetchone()
        return {'data': json.loads(row['payload']), 'updated_at': row['updated_at']} if row else None

    def cache(self, kind, key, payload, account=''):
        with self._connect() as db:
            db.execute('INSERT OR REPLACE INTO companion_cache VALUES (?,?,?,?,?)',
                       (account, kind, key, json.dumps(payload), utc_now()))

    def draft(self, slug, language):
        with self._connect() as db:
            row = db.execute('SELECT payload FROM companion_drafts WHERE slug=? AND language=?',
                             (slug, language)).fetchone()
        return json.loads(row['payload']) if row else None

    def save_draft(self, record, metadata=None, hints=None):
        payload = json.loads(json.dumps(asdict(record)))
        payload['metadata'] = metadata or {}
        payload['hints'] = hints or []
        with self._connect() as db:
            db.execute('INSERT OR REPLACE INTO companion_drafts VALUES (?,?,?)',
                       (record.slug, record.language, json.dumps(payload)))
        return payload

    def operation(self, account, remote_id, slug, kind, payload):
        with self._connect() as db:
            previous = db.execute('SELECT payload FROM companion_operations WHERE account=? AND remote_id=?',
                                  (account, str(remote_id))).fetchone()
            if previous:
                payload = dict(json.loads(previous['payload']), **payload)
            db.execute('INSERT OR REPLACE INTO companion_operations VALUES (?,?,?,?,?,?)',
                       (account, str(remote_id), slug, kind, json.dumps(payload), utc_now()))

    def favorites(self):
        with self._connect() as db:
            rows = db.execute("SELECT payload FROM companion_cache WHERE account='' AND kind='local_favorite'").fetchall()
        return [json.loads(row['payload']) for row in rows if json.loads(row['payload']).get('favorite')]

    def operations(self, account, slug=None):
        with self._connect() as db:
            rows = db.execute('SELECT * FROM companion_operations WHERE account=? ORDER BY updated_at DESC',
                              (account,)).fetchall()
        return [dict(row, payload=json.loads(row['payload'])) for row in rows if not slug or row['slug'] == slug]

    def clear_private(self):
        with self._connect() as db:
            db.execute("DELETE FROM companion_cache WHERE account != ''")
            db.execute('DELETE FROM companion_operations')
            rows = db.execute('SELECT slug,language,payload FROM companion_drafts').fetchall()
            for row in rows:
                if json.loads(row['payload']).get('account'):
                    db.execute('DELETE FROM companion_drafts WHERE slug=? AND language=?', (row['slug'], row['language']))
