# SPDX-License-Identifier: LicenseRef-Blockscout
"""Bundled blockscout-analysis skill resources."""

import json
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any

from mcp.server.fastmcp.resources import FunctionResource
from mcp.types import Annotations
from pydantic import AnyUrl

from blockscout_mcp_server.constants import SKILL_POINTER_TEXT_TEMPLATE

SKILL_URI_PREFIX = "blockscout-mcp://skill/"
_PACKAGE_NAME = "blockscout_mcp_server"
_BUNDLED_SKILL_DIR = "_bundled_skill"
_MANIFEST_FILE = "_bundled_skill_manifest.json"


def relative_path_to_uri(rel: str) -> str:
    """Convert a bundled-skill relative path to its MCP resource URI."""
    return f"{SKILL_URI_PREFIX}{rel}"


def uri_to_relative_path(uri: str) -> str | None:
    """Return the bundled-skill relative path for a skill URI, or None on miss."""
    if not uri.startswith(SKILL_URI_PREFIX):
        return None
    return uri.removeprefix(SKILL_URI_PREFIX)


def list_resources() -> list[FunctionResource]:
    """Return bundled skill resources sorted by URI."""
    return list(_RESOURCE_LIST)


def read_resource(uri: str) -> str | None:
    """Return precomputed resource body text for a URI, or None on miss."""
    resource = _RESOURCES_BY_URI.get(uri)
    if resource is None:
        return None
    return resource.fn()


def _load_manifest() -> dict[str, Any]:
    try:
        manifest_text = (files(_PACKAGE_NAME) / _MANIFEST_FILE).read_text(encoding="utf-8")
    except FileNotFoundError:
        sidecar_path = Path(__file__).resolve().parents[2] / ".bundle_skill_commit_info.json"
        try:
            manifest_text = sidecar_path.read_text(encoding="utf-8")
        except OSError:
            return {}

    try:
        return json.loads(manifest_text)
    except json.JSONDecodeError:
        return {}


def _strip_frontmatter(body: str) -> tuple[dict[str, str], str]:
    if not body.startswith("---\n"):
        return {}, body

    closing_marker = "\n---\n"
    closing_index = body.find(closing_marker, len("---\n"))
    if closing_index == -1:
        return {}, body

    metadata = _parse_frontmatter(body[len("---\n") : closing_index])
    return metadata, body[closing_index + len(closing_marker) :]


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    lines = frontmatter.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if ":" not in line or line.startswith((" ", "\t")):
            index += 1
            continue

        key, value = line.split(":", 1)
        value = value.strip()
        if value:
            metadata[key.strip()] = _strip_wrapping_quotes(value)
            index += 1
            continue

        continuation: list[str] = []
        index += 1
        while index < len(lines) and lines[index].startswith((" ", "\t")):
            continuation.append(lines[index].strip())
            index += 1
        metadata[key.strip()] = " ".join(continuation).strip()

    return metadata


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _iter_whitelisted_files() -> list[tuple[str, str]]:
    skill_root = files(_PACKAGE_NAME) / _BUNDLED_SKILL_DIR
    if not skill_root.is_dir():
        skill_root = Path(__file__).resolve().parents[2] / "agent-skills" / "blockscout-analysis"
    entries: list[tuple[str, str]] = []

    skill_md = skill_root / "SKILL.md"
    if not skill_md.is_file():
        raise RuntimeError(
            "Bundled blockscout-analysis skill entrypoint is missing. "
            "Initialize the agent-skills submodule or install a package that includes _bundled_skill/SKILL.md."
        )
    entries.append(("SKILL.md", skill_md.read_text(encoding="utf-8")))

    references_root = skill_root / "references"
    if references_root.is_dir():
        for path in references_root.rglob("*.md"):
            if path.is_file():
                rel = str(PurePosixPath(path.relative_to(skill_root)))
                entries.append((rel, path.read_text(encoding="utf-8")))

    return entries


def _resource_annotations(rel: str, last_modified: str | None) -> Annotations:
    kwargs: dict[str, Any] = {}
    if last_modified:
        kwargs["lastModified"] = last_modified

    if rel == "SKILL.md":
        return Annotations(audience=["user", "assistant"], priority=0.9, **kwargs)
    return Annotations(audience=["assistant"], priority=0.2, **kwargs)


def _build_resources() -> tuple[dict[str, FunctionResource], dict[str, FunctionResource], list[FunctionResource]]:
    manifest = _load_manifest()
    last_modified = manifest.get("last_modified") if isinstance(manifest.get("last_modified"), str) else None
    by_uri: dict[str, FunctionResource] = {}
    by_relative_path: dict[str, FunctionResource] = {}

    for rel, raw_body in _iter_whitelisted_files():
        body = raw_body
        description = None
        if rel == "SKILL.md":
            metadata, body = _strip_frontmatter(raw_body)
            description = metadata.get("description") or None

        uri = relative_path_to_uri(rel)
        resource = FunctionResource(
            uri=AnyUrl(uri),
            name=rel,
            description=description,
            mime_type="text/markdown",
            annotations=_resource_annotations(rel, last_modified),
            fn=lambda body=body: body,
            # NOTE: FastMCP drops FunctionResource._meta during the protocol
            # Resource conversion in mcp.list_resources(). If protocol-level
            # _meta is ever needed here, construct mcp.types.Resource directly
            # or override list_resources().
        )
        by_uri[uri] = resource
        by_relative_path[rel] = resource

    resource_list = sorted(by_uri.values(), key=lambda resource: str(resource.uri))
    return by_uri, by_relative_path, resource_list


_RESOURCES_BY_URI, _RESOURCES_BY_RELATIVE_PATH, _RESOURCE_LIST = _build_resources()


def _extract_skill_version(frontmatter: dict[str, str]) -> str | None:
    """Extract the skill version from a parsed frontmatter dict.

    The ``metadata`` key holds a raw JSON string (e.g.
    ``'{"author":"blockscout.com","version":"0.5.0",...}'``).  Returns the
    version string on success, or ``None`` for every off-nominal input —
    missing key, malformed JSON, absent ``version``, or non-string value.
    Never raises.
    """
    raw = frontmatter.get("metadata")
    if not raw:
        return None
    try:
        obj = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    version = obj.get("version") if isinstance(obj, dict) else None
    if not isinstance(version, str):
        return None
    return version


def _load_bundled_skill_version() -> str | None:
    """Read SKILL.md once at import and return the skill version, or None."""
    try:
        entries = _iter_whitelisted_files()
    except RuntimeError:
        return None
    for rel, raw_body in entries:
        if rel == "SKILL.md":
            metadata, _ = _strip_frontmatter(raw_body)
            return _extract_skill_version(metadata)
    return None


_BUNDLED_SKILL_VERSION: str | None = _load_bundled_skill_version()


def get_bundled_skill_version() -> str | None:
    """Return the bundled skill version string, or None if unavailable."""
    return _BUNDLED_SKILL_VERSION


def skill_pointer_text() -> str:
    """Return the skill pointer text, optionally annotated with the bundle version."""
    version = get_bundled_skill_version()
    version_note = f" (version {version})" if version is not None else ""
    return SKILL_POINTER_TEXT_TEMPLATE.format(version_note=version_note)
