"""Shared, IP-based limits for endpoints that start expensive work."""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
