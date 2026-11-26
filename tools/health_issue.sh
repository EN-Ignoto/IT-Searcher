#!/usr/bin/env bash
# Open, update or close the one `searcher-health` issue from a report.
#   tools/health_issue.sh REPORT_FILE STATUS   (STATUS: 0 = healthy, else unhealthy)
# Needs GH_TOKEN with issues:write. Never fails the calling job.
set -uo pipefail
report="$1"
status="$2"
label="searcher-health"
title="Searcher health: needs attention"
gh label create "$label" --color B60205 \
  --description "Opened automatically when the job searcher is unhealthy" --force >/dev/null 2>&1 || true
number="$(gh issue list --label "$label" --state open --json number --jq '.[0].number' 2>/dev/null || true)"
if [ "$status" != "0" ]; then
  if [ -z "$number" ]; then
    gh issue create --title "$title" --label "$label" --body-file "$report" || true
  else
    gh issue edit "$number" --body-file "$report" >/dev/null || true
  fi
elif [ -n "$number" ]; then
  gh issue close "$number" --comment "Recovered: the latest health report passes every check." || true
fi
exit 0
