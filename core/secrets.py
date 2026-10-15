"""
API credential loading from environment variables only.

Credentials are NEVER read from versioned files. This module does not parse
``.env`` files: export the variables in the shell / service manager of the
machine that runs the bot (or ``set -a; source .env; set +a`` from a git-ignored
``.env``). Variable names are listed in ``.env.example``.

Three separate key pairs are supported, one per environment (PLAN §7.9):

- ``spot_demo``        -> BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET
- ``futures_testnet``  -> BINANCE_FUTURES_TESTNET_API_KEY / BINANCE_FUTURES_TESTNET_API_SECRET
- ``live``             -> BINANCE_API_KEY / BINANCE_API_SECRET

Legacy names already used by ``core.config`` (``BINANCE_TESTNET_SECRET`` and
``BINANCE_SECRET``) are accepted as fallbacks for the secret.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, Literal, Mapping, Optional, Tuple

Environment = Literal["spot_demo", "futures_testnet", "live"]

# env -> (key variable, secret variables in priority order)
ENV_VARS: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "spot_demo": ("BINANCE_TESTNET_API_KEY", ("BINANCE_TESTNET_API_SECRET", "BINANCE_TESTNET_SECRET")),
    "futures_testnet": ("BINANCE_FUTURES_TESTNET_API_KEY", ("BINANCE_FUTURES_TESTNET_API_SECRET",)),
    "live": ("BINANCE_API_KEY", ("BINANCE_API_SECRET", "BINANCE_SECRET")),
}

# Placeholder values that must never be treated as real credentials
_PLACEHOLDERS = {"", "test", "changeme", "your_api_key_here", "your_secret_here",
                 "your_demo_api_key_here", "your_demo_secret_here"}


class MissingSecretError(RuntimeError):
    """Raised when the credentials of an environment are not set."""


def mask(value: Optional[str]) -> str:
    """Return a non-reversible representation of a secret, safe for logs."""
    if not value:
        return "<unset>"
    if len(value) <= 8:
        return "****"
    return f"{value[:2]}...{value[-2:]} (len={len(value)})"


@dataclass(frozen=True)
class ApiCredentials:
    """API key pair. ``repr``/``str`` never expose the values."""

    environment: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"ApiCredentials(environment={self.environment!r}, api_key={mask(self.api_key)})"

    __str__ = __repr__


def _lookup(names: Tuple[str, ...], environ: Mapping[str, str]) -> str:
    for name in names:
        value = environ.get(name, "").strip()
        if value:
            return value
    return ""


def get_credentials(environment: Environment, environ: Optional[Mapping[str, str]] = None) -> ApiCredentials:
    """
    Read the key pair of ``environment`` from environment variables.

    Args:
        environment: 'spot_demo', 'futures_testnet' or 'live'
        environ: mapping to read from (defaults to ``os.environ``; used by tests)

    Raises:
        ValueError: unknown environment
        MissingSecretError: key or secret unset (the message names the
            variables, never their values)
    """
    if environment not in ENV_VARS:
        raise ValueError(f"Unknown environment {environment!r}; expected one of {sorted(ENV_VARS)}")
    env = os.environ if environ is None else environ
    key_var, secret_vars = ENV_VARS[environment]
    api_key = _lookup((key_var,), env)
    api_secret = _lookup(secret_vars, env)
    missing = []
    if api_key.lower() in _PLACEHOLDERS:
        missing.append(key_var)
    if api_secret.lower() in _PLACEHOLDERS:
        missing.append(secret_vars[0])
    if missing:
        raise MissingSecretError(
            f"Credentials for '{environment}' are not set: export {', '.join(missing)} "
            "(see .env.example; secrets are read from environment variables only)"
        )
    return ApiCredentials(environment=environment, api_key=api_key, api_secret=api_secret)


def has_credentials(environment: Environment, environ: Optional[Mapping[str, str]] = None) -> bool:
    """True if ``get_credentials(environment)`` would succeed."""
    try:
        get_credentials(environment, environ)
        return True
    except MissingSecretError:
        return False


def redact(text: str, *secrets: Optional[str]) -> str:
    """Replace every occurrence of the given secrets in ``text`` by a mask."""
    for s in secrets:
        if s and len(s) >= 4:
            text = text.replace(s, "<redacted>")
    return text
