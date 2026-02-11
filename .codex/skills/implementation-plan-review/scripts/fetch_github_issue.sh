#!/usr/bin/env bash
#
# Fetches a GitHub issue/PR (title + body + labels/state/url) into a local markdown file.
#
# Usage:
#   fetch_github_issue.sh <issue-number> [--out <path>]
#
# Output on success (when --out is used):
#   OK <path>
#
# Output on failure:
#   ERROR <message>
#
# Exit codes:
#   0 - Success
#   1 - Missing/invalid arguments
#   3 - GitHub CLI not authenticated
#   4 - Failed to fetch issue

set -euo pipefail

if [[ $# -lt 1 || -z "${1:-}" ]]; then
    echo "ERROR Missing GitHub issue number argument"
    exit 1
fi

ISSUE_NUMBER="$1"
shift

OUT=""
if [[ $# -gt 0 ]]; then
    if [[ "${1:-}" == "--out" ]]; then
        if [[ $# -lt 2 || -z "${2:-}" ]]; then
            echo "ERROR --out requires a non-empty path"
            exit 1
        fi
        OUT="$2"
        shift 2
    else
        echo "ERROR Unknown argument: ${1:-}"
        exit 1
    fi
fi

if [[ $# -gt 0 ]]; then
    echo "ERROR Too many arguments"
    exit 1
fi

if [[ ! "$ISSUE_NUMBER" =~ ^[0-9]+$ ]]; then
    echo "ERROR Issue number must be digits (example: 326)"
    exit 1
fi

if ! gh auth status &>/dev/null; then
    echo "ERROR GitHub CLI not authenticated. Run: gh auth login"
    exit 3
fi

CMD=(gh issue view "$ISSUE_NUMBER")

set +e
MD="$("${CMD[@]}" --json title,body,url,state,labels --template \
    '{{printf "# %s\n\n" .title -}}
{{printf "Source: %s\n" .url -}}
{{printf "State: %s\n" .state -}}
{{- printf "Labels: " -}}
{{- if .labels -}}
{{- range $i, $l := .labels -}}
{{- if $i -}}, {{- end -}}
{{- $l.name -}}
{{- end -}}
{{- else -}}None{{- end -}}
{{printf "\n\n## Body\n\n%s\n" .body -}}' 2>&1)"
STATUS=$?
set -e

if [[ $STATUS -ne 0 ]]; then
    FIRST_LINE="$(printf "%s" "$MD" | head -n 1)"
    echo "ERROR Failed to fetch issue via gh: ${FIRST_LINE}"
    exit 4
fi

if [[ -n "$OUT" ]]; then
    printf "%s" "$MD" >"$OUT"
    echo "OK $OUT"
else
    printf "%s" "$MD"
fi
