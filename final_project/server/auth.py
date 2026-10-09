"""Token configuration and constant-time checks; never log or repr secrets."""
from dataclasses import dataclass, field
import hmac
import os
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class AuthConfig:
    admin_token: str = field(repr=False)
    coach_tokens: Mapping[str, str] = field(repr=False)

    def __post_init__(self):
        tokens = [self.admin_token, *self.coach_tokens.values()]
        if not self.coach_tokens or any(not isinstance(t, str) or not 16 <= len(t) <= 1024 or t.startswith('REPLACE_') or t == 'dev-token' for t in tokens):
            raise ValueError('Missing or placeholder authentication configuration')
        if len(set(tokens)) != len(tokens):
            raise ValueError('Authentication tokens must be distinct')
        object.__setattr__(self, 'coach_tokens', MappingProxyType(dict(self.coach_tokens)))

    @classmethod
    def from_env(cls, coach_ids: list[str], environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        names = [f'FINAL_PROJECT_COACH_TOKEN_{cid.upper()}' for cid in coach_ids]
        if len(set(names)) != len(names):
            raise ValueError('Coach environment names collide')
        return cls(env.get('FINAL_PROJECT_ADMIN_TOKEN', ''),
                   {cid: env.get(name, '') for cid, name in zip(coach_ids, names)})

    def check(self, role: str, token: object, coach_id: str | None = None) -> bool:
        if not isinstance(token, str) or len(token) > 1024:
            return False
        expected = self.admin_token if role == 'admin' else self.coach_tokens.get(coach_id) if role == 'coach' else None
        return expected is not None and hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8'))
