# SPDX-License-Identifier: LicenseRef-Blockscout
"""Shared request/context test doubles for the analytics test modules.

``tests/test_analytics.py`` and ``tests/test_analytics_identity.py`` exercise the
same analytics entry points and previously each carried an identical copy of
these two doubles. Centralizing them here keeps the shape they emulate — the
minimal attribute surface :mod:`blockscout_mcp_server.analytics` reads — defined
in one place:

- :class:`DummyRequest` mimics a starlette ``Request`` just enough for IP
  extraction: a ``headers`` mapping and a ``client.host`` fallback.
- :class:`DummyCtx` mimics an MCP context just enough for client-metadata
  extraction: ``request_context.request`` (``None`` when built without a
  request) and ``session.client_params.clientInfo``.
"""

from __future__ import annotations

import types


class DummyRequest:
    def __init__(self, headers=None, host="127.0.0.1"):
        self.headers = headers or {}
        self.client = types.SimpleNamespace(host=host)


class DummyCtx:
    def __init__(self, request=None, client_name="", client_version=""):
        self.request_context = types.SimpleNamespace(request=request) if request else None
        clientInfo = types.SimpleNamespace(name=client_name, version=client_version)
        self.session = types.SimpleNamespace(client_params=types.SimpleNamespace(clientInfo=clientInfo))
