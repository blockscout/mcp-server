# SPDX-License-Identifier: LicenseRef-Blockscout
import uuid
from types import SimpleNamespace

from blockscout_mcp_server.analytics import (
    _build_distinct_id,
    _build_fingerprint_distinct_id,
    _extract_request_ip,
)


def test_extract_request_ip_headers_prefer_xff():
    headers = {"x-forwarded-for": "203.0.113.10, 70.41.3.18", "user-agent": "UA-1"}
    request = SimpleNamespace(headers=headers, client=SimpleNamespace(host="198.51.100.2"))
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))
    ip = _extract_request_ip(ctx)
    assert ip == "203.0.113.10"


def test_extract_request_ip_fallbacks():
    # No xff, but X-Real-IP present
    headers = {"X-Real-IP": "192.0.2.9", "User-Agent": "UA-2"}
    request = SimpleNamespace(headers=headers, client=SimpleNamespace(host="10.0.0.1"))
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))
    ip = _extract_request_ip(ctx)
    assert ip == "192.0.2.9"

    # Nothing in headers, fallback to client.host
    headers2 = {}
    request2 = SimpleNamespace(headers=headers2, client=SimpleNamespace(host="10.0.0.5"))
    ctx2 = SimpleNamespace(request_context=SimpleNamespace(request=request2))
    ip2 = _extract_request_ip(ctx2)
    assert ip2 == "10.0.0.5"


def test_extract_request_ip_precedence_when_both_headers_present():
    headers = {"X-Forwarded-For": "198.51.100.10, 203.0.113.20", "X-Real-IP": "192.0.2.9"}
    request = SimpleNamespace(headers=headers, client=SimpleNamespace(host="10.0.0.1"))
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))
    ip = _extract_request_ip(ctx)
    # Prefer X-Forwarded-For, left-most IP
    assert ip == "198.51.100.10"


def test_extract_request_ip_case_insensitive_headers():
    headers = {"X-Forwarded-For": "203.0.113.30"}
    request = SimpleNamespace(headers=headers, client=SimpleNamespace(host="10.0.0.1"))
    ctx = SimpleNamespace(request_context=SimpleNamespace(request=request))
    ip = _extract_request_ip(ctx)
    assert ip == "203.0.113.30"


def test_build_distinct_id_stable():
    # Same inputs must produce same UUID
    a = _build_distinct_id("1.2.3.4", "client", "1.0")
    b = _build_distinct_id("1.2.3.4", "client", "1.0")
    assert a == b

    # Changing any component changes the result
    c = _build_distinct_id("1.2.3.4", "client", "1.1")
    assert c != a
    d = _build_distinct_id("5.6.7.8", "client", "1.0")
    assert d != a
    e = _build_distinct_id("1.2.3.4", "clientZ", "1.0")
    assert e != a


def test_build_fingerprint_distinct_id_golden_vector():
    # Hard-coded literal, independent of the implementation under test: pins the exact
    # derivation recipe (UUIDv5, NAMESPACE_URL, namespace URL string, "key:" tag).
    fingerprint = "ab" * 32
    assert _build_fingerprint_distinct_id(fingerprint) == "4013a9cf-f61d-58d9-8ef7-63557e02c5e0"


def test_build_fingerprint_distinct_id_stable():
    fingerprint = "cd" * 32
    a = _build_fingerprint_distinct_id(fingerprint)
    b = _build_fingerprint_distinct_id(fingerprint)
    assert a == b


def test_build_fingerprint_distinct_id_distinctness():
    a = _build_fingerprint_distinct_id("ab" * 32)
    b = _build_fingerprint_distinct_id("cd" * 32)
    assert a != b


def test_build_fingerprint_distinct_id_output_shape():
    result = _build_fingerprint_distinct_id("ab" * 32)
    # Must be parseable as a valid UUID string, like the legacy helper's output.
    assert str(uuid.UUID(result)) == result


def test_build_fingerprint_distinct_id_domain_separation_from_legacy():
    fingerprint = "ab" * 32
    fp_id = _build_fingerprint_distinct_id(fingerprint)

    # A client name or IP that happens to equal the digest must not collide with the
    # fingerprint identity.
    legacy_as_client_name = _build_distinct_id("", fingerprint, "")
    legacy_as_ip = _build_distinct_id(fingerprint, "", "")
    assert fp_id != legacy_as_client_name
    assert fp_id != legacy_as_ip


def test_build_fingerprint_distinct_id_cross_basis_distinctness():
    fingerprint = "ab" * 32
    fp_id = _build_fingerprint_distinct_id(fingerprint)
    legacy_id = _build_distinct_id("1.2.3.4", "some-client", "1.0")
    assert fp_id != legacy_id
