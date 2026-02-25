"""
CRIT-5: Slack HMAC signature verification unit test.

Verifies that `hmac.new(key, msg, hashlib.sha256)` is the correct call
for Python 3.11 and that the SlackInterface._verify_slack_signature logic
produces the expected output for a known key/body/timestamp combination.

These tests do NOT require a live Slack workspace.
"""

import hashlib
import hmac
import time


# ──────────────────────────────────────────────────────────────────────────────
# Low-level hmac.new() correctness
# ──────────────────────────────────────────────────────────────────────────────

def test_hmac_new_exists_in_python3():
    """hmac.new() is a valid Python 3 function (not removed in Py3)."""
    assert callable(hmac.new), "hmac.new must be callable"


def test_hmac_new_with_hashlib_sha256_constructor():
    """
    hmac.new() accepts hashlib.sha256 (the constructor) as digestmod.

    This is the exact call pattern used in SlackInterface._verify_slack_signature.
    Passing the constructor (not an instance) is the documented Python 3 style.
    """
    key = b"test_signing_secret"
    msg = b"v0:1234567890:body=hello"
    mac = hmac.new(key, msg, hashlib.sha256)
    digest = mac.hexdigest()
    assert isinstance(digest, str)
    assert len(digest) == 64  # SHA-256 hex digest is always 64 chars


def test_hmac_new_produces_stable_output():
    """Same key + msg always produces the same digest."""
    key = b"stable_key"
    msg = b"stable_message"
    digest1 = hmac.new(key, msg, hashlib.sha256).hexdigest()
    digest2 = hmac.new(key, msg, hashlib.sha256).hexdigest()
    assert digest1 == digest2


def test_hmac_new_different_keys_produce_different_digests():
    """Different keys produce different digests for the same message."""
    msg = b"same_message"
    digest1 = hmac.new(b"key_a", msg, hashlib.sha256).hexdigest()
    digest2 = hmac.new(b"key_b", msg, hashlib.sha256).hexdigest()
    assert digest1 != digest2


# ──────────────────────────────────────────────────────────────────────────────
# SlackInterface signature verification logic (inline, no import needed)
# ──────────────────────────────────────────────────────────────────────────────

def _verify_slack_signature(signing_secret: str, body: bytes, timestamp: str, signature: str) -> bool:
    """
    Mirror of SlackInterface._verify_slack_signature for isolated testing.
    """
    if not signature:
        return False

    try:
        parsed_timestamp = int(timestamp)
    except (TypeError, ValueError):
        return False

    if abs(time.time() - parsed_timestamp) > 300:
        return False

    sig_basestring = f"v0:{parsed_timestamp}:{body.decode('utf-8')}"
    my_signature = (
        "v0="
        + hmac.new(
            signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(my_signature, signature)


def test_slack_signature_valid():
    """A correctly generated signature verifies successfully."""
    secret = "my_slack_signing_secret"
    timestamp = str(int(time.time()))
    body = b"payload=test_body"
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    correct_sig = (
        "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    )
    assert _verify_slack_signature(secret, body, timestamp, correct_sig) is True


def test_slack_signature_wrong_secret():
    """A signature generated with a different secret is rejected."""
    real_secret = "real_secret"
    wrong_secret = "wrong_secret"
    timestamp = str(int(time.time()))
    body = b"payload=test_body"
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    sig_with_wrong_key = (
        "v0=" + hmac.new(wrong_secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    )
    assert _verify_slack_signature(real_secret, body, timestamp, sig_with_wrong_key) is False


def test_slack_signature_stale_timestamp():
    """Requests older than 5 minutes are rejected regardless of signature."""
    secret = "any_secret"
    old_timestamp = str(int(time.time()) - 400)  # 400s ago > 300s threshold
    body = b"payload=irrelevant"
    sig_basestring = f"v0:{old_timestamp}:{body.decode()}"
    valid_sig = (
        "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    )
    assert _verify_slack_signature(secret, body, old_timestamp, valid_sig) is False


def test_slack_signature_tampered_body():
    """Signature computed on original body does not verify for a modified body."""
    secret = "signing_secret"
    timestamp = str(int(time.time()))
    original_body = b"original_payload"
    tampered_body = b"tampered_payload"
    sig_basestring = f"v0:{timestamp}:{original_body.decode()}"
    sig_for_original = (
        "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    )
    assert _verify_slack_signature(secret, tampered_body, timestamp, sig_for_original) is False


def test_slack_signature_invalid_timestamp_header():
    """Malformed timestamp headers are rejected instead of raising errors."""
    secret = "my_secret"
    body = b"payload=test"
    assert _verify_slack_signature(secret, body, "not-a-timestamp", "v0=fake") is False


def test_slack_signature_missing_header():
    """Missing signature headers are rejected."""
    secret = "my_secret"
    body = b"payload=test"
    timestamp = str(int(time.time()))
    assert _verify_slack_signature(secret, body, timestamp, "") is False
