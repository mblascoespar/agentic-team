#!/usr/bin/env python3
"""
Standalone observability report for the MCP engine event log.

Usage:
    python observe.py [--log-path PATH]

--log-path defaults to LOG_PATH env var, then engine/logs/events.jsonl.
Standard library only — no third-party dependencies.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path


def load_events(log_path: Path) -> list:
    if not log_path.exists():
        return []
    events = []
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def analyse(events: list) -> dict:
    exit_events = [e for e in events if e.get("event_type") == "exit"]

    sessions = defaultdict(lambda: {"total": 0, "writes": 0, "reads": 0, "errors": 0, "max_revision": None})
    for e in exit_events:
        sid = e.get("session_id", "unknown")
        s = sessions[sid]
        s["total"] += 1
        if e.get("tool_name") == "write_artifact" and e.get("result_status") == "ok":
            s["writes"] += 1
            rv = e.get("result_version")
            if rv is not None:
                s["max_revision"] = max(s["max_revision"] or 0, rv)
        if e.get("tool_name") == "read_artifact" and e.get("result_status") == "ok":
            s["reads"] += 1
        if e.get("result_status") == "error":
            s["errors"] += 1

    # Collect highest version_reached per slug+stage+session for revision loops
    revision_key_max: dict = {}
    for e in exit_events:
        if e.get("tool_name") == "write_artifact" and e.get("result_status") == "ok":
            rv = e.get("result_version")
            if rv is not None and rv >= 2:
                key = (e.get("slug"), e.get("stage"), e.get("session_id"))
                revision_key_max[key] = max(revision_key_max.get(key, 0), rv)

    revision_loops = [
        {"slug": k[0], "stage": k[1], "session_id": k[2], "version_reached": v}
        for k, v in revision_key_max.items()
    ]

    read_counts: dict = defaultdict(int)
    for e in exit_events:
        if e.get("tool_name") == "read_artifact" and e.get("result_status") == "ok":
            key = (e.get("slug"), e.get("stage"), e.get("read_version"), e.get("session_id"))
            read_counts[key] += 1
    redundant_reads = [
        {"slug": k[0], "stage": k[1], "version": k[2], "session_id": k[3], "count": v}
        for k, v in read_counts.items() if v >= 2
    ]

    error_counts: dict = defaultdict(int)
    for e in exit_events:
        if e.get("result_status") == "error":
            ec = e.get("error_class") or "unknown"
            error_counts[ec] += 1
    total_errors = sum(error_counts.values())
    total_exits = len(exit_events)
    error_distribution = [
        {
            "error_class": ec,
            "count": cnt,
            "pct": round(cnt / total_exits * 100, 1) if total_exits > 0 else 0.0,
        }
        for ec, cnt in sorted(error_counts.items(), key=lambda x: -x[1])
    ] if total_errors > 0 else []

    premature_approvals = sum(
        1 for e in exit_events
        if e.get("tool_name") == "approve_artifact" and e.get("result_status") == "error"
    )
    severe_revision_loops = sum(1 for r in revision_loops if r["version_reached"] >= 3)

    return {
        "sessions": dict(sessions),
        "revision_loops": revision_loops,
        "redundant_reads": redundant_reads,
        "error_distribution": error_distribution,
        "premature_approvals": premature_approvals,
        "severe_revision_loops": severe_revision_loops,
    }


def format_output(results: dict) -> str:
    lines = []

    lines.append("Per-session summary")
    header = f"  {'session_id':<36} | {'total':>5} | {'writes':>6} | {'reads':>5} | {'errors':>6} | max revision"
    lines.append(header)
    for sid, s in results["sessions"].items():
        lines.append(
            f"  {sid:<36} | {s['total']:>5} | {s['writes']:>6} | {s['reads']:>5} | {s['errors']:>6} | {s['max_revision'] or '-'}"
        )
    lines.append("")

    lines.append("Revision loops  (write_artifact result_version >= 2)")
    if results["revision_loops"]:
        lines.append(f"  {'slug':<25} | {'stage':<18} | {'session_id':<36} | version reached")
        for r in results["revision_loops"]:
            lines.append(
                f"  {str(r['slug']):<25} | {str(r['stage']):<18} | {str(r['session_id']):<36} | {r['version_reached']}"
            )
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Redundant reads  (same slug+stage+read_version twice in one session)")
    if results["redundant_reads"]:
        lines.append(f"  {'slug':<25} | {'stage':<18} | {'version':>7} | {'session_id':<36} | count")
        for r in results["redundant_reads"]:
            lines.append(
                f"  {str(r['slug']):<25} | {str(r['stage']):<18} | {str(r['version']):>7} | {str(r['session_id']):<36} | {r['count']}"
            )
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Error distribution")
    if results["error_distribution"]:
        lines.append(f"  {'error_class':<55} | {'count':>5} | % of errors")
        for e in results["error_distribution"]:
            lines.append(f"  {e['error_class']:<55} | {e['count']:>5} | {e['pct']}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("Misbehavior signals")
    lines.append(f"  Premature approvals (approve_artifact errors): {results['premature_approvals']}")
    lines.append(f"  Revision loops (write result_version >= 3): {results['severe_revision_loops']}")

    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MCP engine observability report")
    parser.add_argument("--log-path", default=None, help="Path to events.jsonl")
    args = parser.parse_args(argv)

    if args.log_path:
        log_path = Path(args.log_path)
    else:
        log_path = Path(os.getenv("LOG_PATH", "engine/logs/events.jsonl"))

    events = load_events(log_path)
    if not events:
        print("No events recorded yet.")
        return 0

    print(format_output(analyse(events)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
