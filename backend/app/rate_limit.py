"""Shared SlowAPI limiter instance (architecture §14.4). Per-IP limits on public
auth endpoints; per-user limits on authenticated endpoints once those exist.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
