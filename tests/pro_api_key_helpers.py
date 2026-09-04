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
- :func:`ctx_with_headers` is the multi-header counterpart of
  :func:`ctx_with_header`: real Starlette ``Headers`` with every name
  upper-cased, for well-formed multi-header precedence cases.
- :func:`ctx_with_malformed_headers` is the multi-header counterpart of
  :func:`ctx_with_malformed_header`: a plain ``dict``, for mixes that include a
  malformed value real Starlette ``Headers`` would refuse to encode.
"""

from __future__ import annotations

from collections.abc import Mapping
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


def ctx_with_headers(headers_map: Mapping[str, str]) -> SimpleNamespace:
    """Build a minimal MCP-like context carrying several headers at once.

    Real :class:`starlette.datastructures.Headers` are used with every name
    upper-cased so the case-insensitive lookup path is exercised for the
    fallback header too. Use it for well-formed multi-header precedence cases.
    """
    headers = Headers(headers={name.upper(): value for name, value in headers_map.items()})
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))


def ctx_with_malformed_headers(headers_map: Mapping[str, str]) -> SimpleNamespace:
    """Build a multi-header context whose values bypass starlette's encoding checks.

    A plain ``dict`` is used so a mix that includes a value real
    :class:`starlette.datastructures.Headers` would refuse to encode (control
    characters, over-length) can still be injected. Header names keep their
    given casing; extraction is case-insensitive regardless.
    """
    headers = dict(headers_map)
    request = SimpleNamespace(headers=headers)
    return SimpleNamespace(request_context=SimpleNamespace(request=request))
