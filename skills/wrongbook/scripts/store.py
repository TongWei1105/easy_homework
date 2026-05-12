#!/usr/bin/env python3
"""File-based wrongbook store. No database — each session is one JSON file.

Subcommands:
  add <input.json>           Save a session (copies into <store-dir>/<id>.json)
  query [filters]            Output a generate_pdf-ready JSON
  stats                      Print summary counts
  list-sessions              Print recent sessions

Default store dir: ./output/sessions/  (override with --store-dir)
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_STORE = Path("output/sessions")


# ---------- io helpers ----------

def _ensure_store(store: Path) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    return store


def _new_session_id(store: Path) -> str:
    base = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = base
    n = 1
    while (store / f"{candidate}.json").exists():
        n += 1
        candidate = f"{base}_{n:02d}"
    return candidate


def _load_session(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[wrongbook.store] Skipping {path.name}: {e}", file=sys.stderr)
        return None


def _iter_sessions(store: Path):
    if not store.exists():
        return
    for p in sorted(store.glob("*.json")):
        s = _load_session(p)
        if s is not None:
            yield p, s


# ---------- subcommands ----------

def cmd_add(args) -> int:
    src = Path(args.input)
    if not src.exists():
        print(f"[wrongbook.store] Input not found: {src}", file=sys.stderr)
        return 2

    data = json.loads(src.read_text(encoding="utf-8"))
    questions = data.get("questions") or []
    if not questions:
        print("[wrongbook.store] No questions in input; nothing saved.", file=sys.stderr)
        return 1

    store = _ensure_store(args.store_dir)
    sid = _new_session_id(store)
    out_path = store / f"{sid}.json"

    # Normalize: drop per-question id (regenerated on query), add created_at + id.
    norm_questions = []
    for q in questions:
        nq = {k: q.get(k) for k in (
            "source_qid", "subject", "type", "content",
            "student_answer", "answer_lines", "knowledge_points",
        ) if q.get(k) is not None}
        nq.setdefault("answer_lines", 3)
        norm_questions.append(nq)

    record = {
        "id": sid,
        "title": data.get("title"),
        "student": data.get("student"),
        "image_paths": data.get("image_paths") or [],
        "created_at": data.get("created_at") or datetime.now().isoformat(timespec="seconds"),
        "questions": norm_questions,
    }
    out_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[wrongbook.store] Saved session {sid} ({len(norm_questions)} mistakes) → {out_path}")
    return 0


def _matches(q: dict, session: dict, args) -> bool:
    if args.subject and q.get("subject") != args.subject:
        return False
    if args.type and q.get("type") != args.type:
        return False
    if args.session_id and session.get("id") != args.session_id:
        return False
    created = session.get("created_at", "")
    if args.since and created < args.since:
        return False
    if args.until and created > args.until:
        return False
    if args.last_days is not None:
        cutoff = (datetime.now() - timedelta(days=args.last_days)).isoformat(timespec="seconds")
        if created < cutoff:
            return False
    return True


def cmd_query(args) -> int:
    matched: list[dict] = []
    for _, session in _iter_sessions(args.store_dir):
        for q in session.get("questions", []):
            if _matches(q, session, args):
                matched.append(q)

    if args.random:
        import random
        random.shuffle(matched)
    if args.limit:
        matched = matched[: int(args.limit)]

    questions = []
    for i, q in enumerate(matched, start=1):
        questions.append({
            "id": i,
            **{k: q.get(k) for k in (
                "source_qid", "subject", "type", "content",
                "student_answer", "answer_lines",
            ) if q.get(k) is not None},
        })

    out = {
        "title": args.title or f"错题练习 · {datetime.now():%Y-%m-%d}",
        "student": args.student,
        "questions": questions,
    }
    payload = json.dumps(out, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(payload, encoding="utf-8")
        print(f"[wrongbook.store] Wrote {len(questions)} questions → {args.output}")
    else:
        print(payload)
    return 0


def cmd_stats(args) -> int:
    sessions: list[dict] = []
    by_subject: Counter[str] = Counter()
    by_month: Counter[str] = Counter()
    total = 0

    for _, s in _iter_sessions(args.store_dir):
        sessions.append(s)
        for q in s.get("questions", []):
            total += 1
            by_subject[q.get("subject") or "(unknown)"] += 1
        m = (s.get("created_at") or "")[:7]
        if m:
            by_month[m] += len(s.get("questions", []))

    print(f"Store dir: {args.store_dir}")
    print(f"Total mistakes: {total}   Sessions: {len(sessions)}")
    if by_subject:
        print("\nBy subject:")
        for subj, n in by_subject.most_common():
            print(f"  {subj:<10} {n}")
    if by_month:
        print("\nBy month (latest 6):")
        for m in sorted(by_month, reverse=True)[:6]:
            print(f"  {m}  {by_month[m]}")
    return 0


def cmd_list_sessions(args) -> int:
    rows = []
    for _, s in _iter_sessions(args.store_dir):
        rows.append((
            s.get("id", ""),
            s.get("created_at", ""),
            s.get("student") or "-",
            len(s.get("questions", [])),
            s.get("title") or "",
        ))
    rows.sort(key=lambda r: r[1], reverse=True)
    rows = rows[: args.limit]

    if not rows:
        print("(no sessions)")
        return 0
    print(f"{'ID':<22}  {'Created':<19}  {'Student':<10}  {'#Q':>3}  Title")
    for sid, created, student, n, title in rows:
        print(f"{sid:<22}  {created:<19}  {student:<10}  {n:>3}  {title}")
    return 0


# ---------- argparse ----------

def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="File-based wrongbook store")
    p.add_argument("--store-dir", type=Path, default=DEFAULT_STORE,
                   help=f"Directory holding session JSONs (default: {DEFAULT_STORE})")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="Save a session JSON")
    a.add_argument("input", type=Path)
    a.set_defaults(func=cmd_add)

    q = sub.add_parser("query", help="Output a generate_pdf-ready JSON across sessions")
    q.add_argument("--subject")
    q.add_argument("--type")
    q.add_argument("--session-id")
    q.add_argument("--since", help="ISO datetime, e.g. 2026-05-01")
    q.add_argument("--until", help="ISO datetime")
    q.add_argument("--last-days", type=int, help="Only include mistakes from the last N days")
    q.add_argument("--limit", type=int)
    q.add_argument("--random", action="store_true", help="Shuffle results")
    q.add_argument("--title", help="Override output JSON title")
    q.add_argument("--student", help="Set student name in output JSON")
    q.add_argument("--output", "-o", type=Path, help="Write to file instead of stdout")
    q.set_defaults(func=cmd_query)

    sub.add_parser("stats", help="Print summary counts").set_defaults(func=cmd_stats)

    ls = sub.add_parser("list-sessions", help="Print recent sessions")
    ls.add_argument("--limit", type=int, default=20)
    ls.set_defaults(func=cmd_list_sessions)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
