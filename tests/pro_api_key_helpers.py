# SPDX-License-Identifier: LicenseRef-Blockscout
"""Shared builders for MCP-like request contexts used across PRO API key tests.

Several test modules independently reconstructed the same request-context shape
to exercise client PRO API key extraction. Centralizing the two flavors here
keeps them in one place and makes the header-encoding contract explicit:

- :func:`ctx_with_header` uses real :class:`starlette.datastructures.Headers`
  and passes the header name in non-canonical (upper) casing so the
  case-insensitive lookup path is exercised. Use it for well-formed values.
- :func:`ctx_with_malformed_header` uses a plain ``dict`` so a value that real
  starlette ``Headers`` would refuse to latin-1 encode (control characters,
  over-length) can still be injected; extraction only needs a case-insensitive
  ``Mapping`` lookup.
"""

from __future__ import annotations

from types import SimpleNamespace

from starlette.datastructures import Headers


def ctx_with_header(header_name: str, header_value: str) -> SimpleNamespace:
    """Build a minimal MCP-like context carrying *header_value* under *header_name*.

    Real :class:`starlette.datastructures.Headers` are used with the header name
    upper-cased so the case-insensitive lookup path is exercised.
    """
    headers = Headers(headers={header_name.upper(): header_value})
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def ctx_with_malformed_header(header_name: str, header_value: str) -> SimpleNamespace:
    """Build a context whose header value bypasses starlette's encoding checks.

    A plain ``dict`` is used so a value real :class:`starlette.datastructures.Headers`
    would refuse to encode (control characters, over-length) can still be
    injected. The header name keeps its given casing; extraction is
    case-insensitive regardless.
    """
    headers = {header_name: header_value}
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))
