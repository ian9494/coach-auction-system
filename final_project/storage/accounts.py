"""Coach account authority, separate from auction snapshots in the same project DB."""
import asyncio
import hashlib
import hmac
import re
import secrets
import sqlite3


def valid_account(username, password):
    return (isinstance(username, str) and re.fullmatch(r'[A-Za-z0-9_]{4,32}', username) is not None
            and isinstance(password, str) and 10 <= len(password) <= 128)


def password_key(password, salt):
    return hashlib.scrypt(password.encode('utf-8'), salt=salt, n=16384, r=8, p=1)


class AccountStore:
    def __init__(self, config):
        # SQLiteRepository must initialize/version the DB first. No snapshot schema changes.
        self.connection = sqlite3.connect(config.path(config.sqlite_file))
        with self.connection:
            self.connection.execute('CREATE TABLE IF NOT EXISTS coach_accounts ('
                'username TEXT PRIMARY KEY, coach_id TEXT NOT NULL UNIQUE, '
                'salt BLOB NOT NULL, password_hash BLOB NOT NULL)')
        self._hash_slots = asyncio.Semaphore(4)

    def claimed(self, coach_id):
        return self.connection.execute('SELECT 1 FROM coach_accounts WHERE coach_id=?', (coach_id,)).fetchone() is not None

    async def register(self, username, password, coach_id):
        if not valid_account(username, password): return 'INVALID_ACCOUNT'
        username = username.lower()
        salt = secrets.token_bytes(16)
        async with self._hash_slots:
            key = await asyncio.to_thread(password_key, password, salt)
        try:
            with self.connection:
                self.connection.execute('INSERT INTO coach_accounts VALUES (?,?,?,?)', (username, coach_id, salt, key))
        except sqlite3.IntegrityError:
            return 'ACCOUNT_OR_SEAT_TAKEN'
        return None

    async def authenticate(self, username, password):
        if not valid_account(username, password): return None
        row = self.connection.execute('SELECT coach_id,salt,password_hash FROM coach_accounts WHERE username=?',
                                      (username.lower(),)).fetchone()
        # Unknown usernames still perform a password hash; never return password material.
        salt = row[1] if row else bytes(16)
        async with self._hash_slots:
            key = await asyncio.to_thread(password_key, password, salt)
        return row[0] if row and hmac.compare_digest(key, row[2]) else None

    def close(self):
        self.connection.close()
