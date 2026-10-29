#!/usr/bin/env python3
"""
Continuity engine: a personal ledger that can be handed over.

Headline: nothing drops when a person, a shift, or a day changes.
Files are the truth. The model drafts. Code enforces.

Four commands only:
  pickup    - morning hook: state, open follow-ups, today's checklist
  checklist - write/update today's checklist from files (re-running updates it)
  followup  - bring all open F numbers to bear; --close Fxx attempts a close
  wrapup    - close the day, carry open items forward

Token Factory / Nemotron:
  If NEBIUS_TOKEN_FACTORY_API_KEY is set, pickup may call
  https://api.tokenfactory.nebius.com/v1/chat/completions with model
  nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B to draft a morning summary from
  file context. The key is read ONLY from that environment variable.
  It is never printed, logged, embedded, or stored by this code.
  If no key is set, the app runs in clearly labelled DEMO MODE: summaries
  are file-generated, and no live Token Factory call is made or claimed.

Code-enforced verify:
  followup --close Fxx refuses, with a non-zero exit, if the F file's
  Evidence field is empty, "none", "pending", "tbc", or "n/a".
  No prompt, no model, and no flag can bypass that check in this code.
  A successful close appends a reusable known-fix entry (compounding).

Structure-first retrieval (Oct 29, 2026):
  Retrieval picks a document type first, in priority order, then the
  best matching section inside that document, then answers only from
  that section, citing file + section/id. This is inspired by
  structure-aware retrieval in general, it is NOT an implementation
  of STAIR, it is NOT embedding-based, and it makes no benchmark claim.
  Scoring inside a section is keyword token overlap on structured
  files. A priority tier claims a question only at >= 0.50, unless
  a later tier beats it by more than 0.15. If no section scores
  >= 0.30, the answer is NOT IN DOCS.

Sample data only. No work code, no work SOOs, no real site names.
Standard library only.
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

MODEL = "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"
API_URL = "https://api.tokenfactory.nebius.com/v1/chat/completions"
DEMO_DATE = "2026-10-29"
STOPWORDS = {
    "the", "and", "for", "with", "what", "how", "should", "after",
    "from", "that", "this", "sample", "first", "check", "does", "are",
    "is", "a", "an", "to", "of", "in", "on", "do", "i", "my",
}
EMPTY_EVIDENCE = {"", "none", "pending", "tbc", "n/a", "not yet"}


def vault_dir(args):
    if getattr(args, "vault_dir", None):
        return Path(args.vault_dir)
    env = os.environ.get("CONTINUITY_VAULT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent / "vault"


def read(path):
    return path.read_text(encoding="utf-8") if path.exists() else ""


def parse_field(text, field):
    m = re.search(rf"^{field}:\s*(.*)$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def followups(vault):
    out = []
    d = vault / "followups"
    if not d.exists():
        return out
    for p in sorted(d.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        out.append({
            "id": p.stem,
            "path": p,
            "text": text,
            "owner": parse_field(text, "Owner"),
            "due": parse_field(text, "Due"),
            "status": parse_field(text, "Status").lower(),
            "evidence": parse_field(text, "Evidence"),
            "problem": parse_field(text, "Problem"),
            "do_not": parse_field(text, "Do not"),
        })
    return out


def open_followups(vault):
    return [f for f in followups(vault) if f["status"] == "open"]


def checklist_text(vault):
    lines = ["# Today's checklist", "", f"Date: {DEMO_DATE}", ""]
    lines.append("## Open follow-ups")
    for f in open_followups(vault):
        lines.append(f"- {f['id']}: {f['problem']} (Owner: {f['owner']}, Due: {f['due']})")
    if not open_followups(vault):
        lines.append("- None open.")
    lines.append("")
    lines.append("## Daily checks (from contract.md)")
    contract = read(vault / "contract.md")
    for line in contract.splitlines():
        if line.strip().startswith("- "):
            lines.append(line.strip())
    lines.append("")
    return "\n".join(lines) + "\n"


def token_factory_draft(context, timeout=30):
    """Return (mode, text). Mode is 'live' or 'demo'. Never prints the key."""
    key = os.environ.get("NEBIUS_TOKEN_FACTORY_API_KEY", "").strip()
    if not key:
        return "demo", (
            "DEMO MODE: no live Token Factory call. "
            "No API key was found in NEBIUS_TOKEN_FACTORY_API_KEY, "
            "so this summary is file-generated, not a model call."
        )
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": (
                "Draft a short morning summary from the file context only. "
                "Do not invent facts, sites, or steps. Cite follow-up IDs."
            )},
            {"role": "user", "content": context[:6000]},
        ],
        "temperature": 0.2,
        "max_tokens": 300,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"].strip()
        return "live", f"Token Factory draft ({MODEL}):\n{text}"
    except Exception as e:  # noqa: BLE001 - surface failure, never fake a live call
        return "live-attempt-failed", (
            f"Token Factory call attempted with model {MODEL} and failed: {type(e).__name__}. "
            "Falling back to the file-generated summary below. "
            "No live model output is claimed in this run."
        )


def tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _sections(path):
    """Split one structured file into (label, text) sections.

    known-fixes: one section per KF heading. followups: one section per
    file. SOO / as-built / contract / state / checklist: one section
    per bullet or non-empty line. This is the structure, not chunks.
    """
    text = path.read_text(encoding="utf-8")
    if path.name == "known-fixes.md":
        out = []
        for chunk in text.split("## "):
            chunk = chunk.strip()
            if not chunk:
                continue
            header = chunk.splitlines()[0].strip()
            if header.lower().startswith("kf-"):
                out.append((header, chunk))
        return out
    if path.parent.name == "followups":
        return [(path.stem, text)]
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("- "):
            out.append((path.name, line))
        elif line and not line.startswith("#"):
            out.append((path.name, line))
    return out


def search_structured(vault, question):
    """Structure-first retrieval.

    Tier order, picked first, then best section inside that tier:
    1 known-fixes sections, 2 followups, 3 SOO, 4 as-built,
    5 contract/state/checklist, only as a fallback.
    Returns (score, path, section_label, section_text) or (0, None, "", "").
    A priority tier claims the question only if its best section
    scores >= 0.50. If a later tier beats that tier by more than
    0.15, the later, clearly better section wins instead, so a weak
    high-priority match cannot beat a strong lower-tier match.
    Exception: a known-fix section at >= 0.50 always wins, because
    a compounded fix is the most specific answer for a repeat case.
    If no tier reaches 0.50, the overall best section wins only if
    it scores >= 0.30, otherwise the answer is NOT IN DOCS.
    """
    q = tokens(question)
    if not q:
        return 0.0, None, "", ""
    tiers = [
        sorted(vault.glob("known-fixes.md")),
        sorted((vault / "followups").glob("*.md")) if (vault / "followups").exists() else [],
        sorted(vault.glob("sites/*/soo.md")),
        sorted(vault.glob("sites/*/as-built.md")),
    ]
    fallback = []
    for name in ("contract.md", "state.md", "checklist.md"):
        p = vault / name
        if p.exists():
            fallback.append(p)
    tiers.append(fallback)
    per_tier = []
    for tier in tiers:
        best = (0.0, None, "", "")
        for p in tier:
            for label, section in _sections(p):
                overlap = len(q & tokens(section))
                score = overlap / len(q) if q else 0.0
                if score > best[0]:
                    best = (score, p, label, section)
        per_tier.append(best)
    overall = max(per_tier, key=lambda b: b[0])
    if overall[1] is None or overall[0] < 0.30:
        return 0.0, None, "", ""
    # A compounded known fix at >= 0.50 always wins: it is the most
    # specific answer for a repeat case, and must be cited as KF-.
    if per_tier[0][1] is not None and per_tier[0][0] >= 0.50:
        return per_tier[0]
    for best in per_tier[1:]:
        if best[1] is not None and best[0] >= 0.50 and best[0] >= overall[0] - 0.15:
            return best
    return overall


def search_docs(vault, question):
    """Backward-compatible wrapper: returns (best_score, best_path, best_text)."""
    score, path, _label, section = search_structured(vault, question)
    return score, path, section


def grounded_answer(vault, question):
    score, path, label, section = search_structured(vault, question)
    if path is None or score < 0.30:
        return (
            "NOT IN DOCS: this question is not covered by the sample docs. "
            "No step is invented. Escalate to the sample site lead and "
            "record it as a new follow-up with its source question."
        )
    snippet = section.strip()
    if label and label != path.name:
        snippet = f"{label}: {snippet}"
    return f"Grounded answer, cited from {path.name} section {label} ({path.parent.name}): {snippet}"


def cmd_pickup(args):
    vault = vault_dir(args)
    state = read(vault / "state.md")
    if args.ask:
        print(grounded_answer(vault, args.ask))
        return 0
    print("# Pickup: morning hook")
    print("")
    print(state.rstrip())
    print("")
    print("## Open follow-ups")
    for f in open_followups(vault):
        print(f"- {f['id']}: {f['problem']} (Owner: {f['owner']}, Due: {f['due']})")
    print("")
    print(checklist_text(vault).rstrip())
    mode, draft = token_factory_draft(checklist_text(vault))
    print("")
    print(f"## Model draft [{mode}]")
    print(draft)
    return 0


def cmd_checklist(args):
    vault = vault_dir(args)
    text = checklist_text(vault)
    (vault / "checklist.md").write_text(text, encoding="utf-8")
    print(text.rstrip())
    return 0


def cmd_followup(args):
    vault = vault_dir(args)
    if args.ask:
        print(grounded_answer(vault, args.ask))
        return 0
    if args.close:
        fid = args.close.upper()
        items = {f["id"].upper(): f for f in followups(vault)}
        if fid not in items:
            print(f"REFUSED: follow-up {fid} not found.")
            return 2
        f = items[fid]
        if f["status"] != "open":
            print(f"REFUSED: follow-up {fid} is not open (status: {f['status']}).")
            return 2
        if f["evidence"].lower() in EMPTY_EVIDENCE:
            # Code-enforced verify: refuse, and do not change the file.
            print(
                f"REFUSED: cannot close {fid} by code-enforced verify. "
                f"Evidence is missing ({f['evidence'] or 'empty'}). "
                "Add evidence to the F file first. File unchanged."
            )
            return 2
        # Successful close: update status, then compound into known-fixes.
        new_text = re.sub(
            r"^Status:\s*.*$", "Status: closed", f["text"],
            count=1, flags=re.MULTILINE | re.IGNORECASE,
        )
        f["path"].write_text(new_text, encoding="utf-8")
        kf = vault / "known-fixes.md"
        kf_text = read(kf)
        entry = (
            f"\n## KF-{fid}\n"
            f"Source: {fid}\n"
            f"Problem: {f['problem']}\n"
            f"Fix: {f['evidence']}\n"
            f"Do not: {f['do_not'] or 'Do not close a follow-up without evidence.'}\n"
        )
        if f"KF-{fid}" not in kf_text:
            kf.write_text(kf_text.rstrip() + "\n" + entry, encoding="utf-8")
        print(f"Closed {fid}. Compounded as KF-{fid} in known-fixes.md.")
        return 0
    print("# Follow-ups: all open items")
    for f in open_followups(vault):
        print(f"- {f['id']}: {f['problem']} (Owner: {f['owner']}, Due: {f['due']}, Evidence: {f['evidence']})")
    if not open_followups(vault):
        print("- None open.")
    return 0


def cmd_wrapup(args):
    vault = vault_dir(args)
    open_items = open_followups(vault)
    closed_items = [f for f in followups(vault) if f["status"] == "closed"]
    lines = ["# Wrapup", "", f"Date: {DEMO_DATE}", ""]
    lines.append("## Closed today (from files)")
    for f in closed_items:
        lines.append(f"- {f['id']}: {f['problem']}")
    if not closed_items:
        lines.append("- None closed in this sample run.")
    lines.append("")
    lines.append("## Carried forward (still open)")
    for f in open_items:
        lines.append(f"- {f['id']}: {f['problem']} (Owner: {f['owner']}, Due: {f['due']})")
    if not open_items:
        lines.append("- Nothing carried forward.")
    lines.append("")
    text = "\n".join(lines) + "\n"
    (vault / "wrapup.md").write_text(text, encoding="utf-8")
    print(text.rstrip())
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="continuity")
    parser.add_argument("--vault-dir", default=None, help="Vault directory (default: ./vault)")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pickup", help="Morning hook")
    p.add_argument("--ask", default=None, help="Grounded troubleshooting question")
    p.set_defaults(fn=cmd_pickup)
    c = sub.add_parser("checklist", help="Write/update today's checklist")
    c.set_defaults(fn=cmd_checklist)
    f = sub.add_parser("followup", help="Bring all open F numbers to bear")
    f.add_argument("--close", default=None, help="Attempt to close an F id, e.g. F20 (code-enforced verify)")
    f.add_argument("--ask", default=None, help="Grounded troubleshooting question")
    f.set_defaults(fn=cmd_followup)
    w = sub.add_parser("wrapup", help="Close the day, carry open items forward")
    w.set_defaults(fn=cmd_wrapup)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
