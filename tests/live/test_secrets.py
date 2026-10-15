"""Tests for core.secrets and the repository secret hygiene (no network)."""
import re
import subprocess
from pathlib import Path

import pytest

from core.secrets import ApiCredentials, MissingSecretError, get_credentials, has_credentials, mask, redact

REPO = Path(__file__).resolve().parents[2]

# Tracked files the user decided to keep for now: their keys are pending rotation
# and removal (see the L01/L05 hand-off notes). Everything else must be clean.
PENDING_ROTATION = {".env.futures.backup", "pruebita.ipynb"}

# A Binance API key / secret is 64 alphanumeric chars. HMAC signatures in logged
# URLs (``signature=<64 hex>``) are not secrets and are ignored.
KEY_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z0-9]{64}(?![A-Za-z0-9])")
ASSIGN_RE = re.compile(r"(?i)\b(api[_-]?key|api[_-]?secret|secret[_-]?key|BINANCE_[A-Z_]*(KEY|SECRET))[ \t]*[=:][ \t]*['\"]?([^\s'\"#]+)")
PLACEHOLDER_RE = re.compile(r"(?i)^(your_|<|\$\{|\$|os\.|settings\.|creds\.|env|test$|x+$|k+$|s+$|none$|\"\"$)")


def test_env_vars_only(monkeypatch, tmp_path):
    # A .env file in the working directory must NOT be read
    (tmp_path / ".env").write_text("BINANCE_FUTURES_TESTNET_API_KEY=fromfile\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_KEY", raising=False)
    monkeypatch.delenv("BINANCE_FUTURES_TESTNET_API_SECRET", raising=False)
    with pytest.raises(MissingSecretError) as ei:
        get_credentials("futures_testnet")
    assert "BINANCE_FUTURES_TESTNET_API_KEY" in str(ei.value)
    assert "fromfile" not in str(ei.value)


def test_separate_environments():
    env = {
        "BINANCE_TESTNET_API_KEY": "spotkey123", "BINANCE_TESTNET_API_SECRET": "spotsecret123",
        "BINANCE_FUTURES_TESTNET_API_KEY": "futkey123", "BINANCE_FUTURES_TESTNET_API_SECRET": "futsecret123",
        "BINANCE_API_KEY": "prodkey123", "BINANCE_SECRET": "prodsecret123",  # legacy secret name
    }
    assert get_credentials("spot_demo", env).api_key == "spotkey123"
    assert get_credentials("futures_testnet", env).api_secret == "futsecret123"
    assert get_credentials("live", env).api_secret == "prodsecret123"
    env["BINANCE_API_SECRET"] = "newprodsecret"
    assert get_credentials("live", env).api_secret == "newprodsecret"
    with pytest.raises(ValueError):
        get_credentials("mainnet", env)  # type: ignore[arg-type]


def test_placeholders_are_not_credentials():
    assert not has_credentials("live", {"BINANCE_API_KEY": "test", "BINANCE_SECRET": "test"})
    assert not has_credentials("spot_demo", {"BINANCE_TESTNET_API_KEY": "abc"})


def test_repr_and_mask_never_expose_values():
    c = ApiCredentials("live", "A" * 64, "B" * 64)
    assert "A" * 10 not in repr(c) and "B" * 10 not in repr(c) and "B" * 10 not in str(c)
    assert "B" * 10 not in mask("B" * 64)
    assert redact("key=SECRETVALUE end", "SECRETVALUE") == "key=<redacted> end"


def test_key_pattern_detects_planted_key():
    fake = ("Ab1" * 22)[:64]  # built at runtime so this file stays clean
    assert KEY_RE.search(f"API_KEY={fake}\n")
    assert not KEY_RE.search(f"key={fake}x")  # 65 chars: not a key-shaped token
    assert ASSIGN_RE.search(f"BINANCE_API_SECRET = '{fake}'").group(3) == fake


def _tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True, check=True).stdout
    return [p for p in out.decode().split("\0") if p]


def test_no_api_keys_in_versioned_files():
    try:
        files = _tracked_files()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    offenders = []
    for rel in files:
        if Path(rel).name in PENDING_ROTATION:
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for m in KEY_RE.finditer(text):
            if text[max(0, m.start() - 10):m.start()].endswith("signature="):
                continue
            offenders.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}")
        for m in ASSIGN_RE.finditer(text):
            value = m.group(3)
            if len(value) >= 32 and not PLACEHOLDER_RE.match(value):
                offenders.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1} ({m.group(1)})")
    # Only locations are reported, never the matched values
    assert not offenders, f"possible API keys in versioned files: {offenders}"


def test_env_example_has_names_only():
    for line in (REPO / ".env.example").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, _, value = line.partition("=")
        assert value == "", f".env.example must not carry values ({name})"


def test_gitignore_covers_env_files():
    try:
        ignored = [subprocess.run(["git", "check-ignore", "-q", "--no-index", name], cwd=REPO,
                                  capture_output=True).returncode for name in (".env", ".env.local", ".env.prod")]
        keep = subprocess.run(["git", "check-ignore", "-q", ".env.example"], cwd=REPO, capture_output=True)
    except OSError:
        pytest.skip("git not available")
    assert ignored == [0, 0, 0]
    assert keep.returncode == 1  # .env.example stays versioned
