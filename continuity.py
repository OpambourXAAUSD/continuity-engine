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


def search_docs(vault, question):
    """Search troubleshooting docs only. Returns (best_score, best_path, best_text)."""
    docs = []
    # Known fixes first: a compounded fix is the most specific citation for a repeat case.
    for pattern in ("known-fixes.md", "sites/*/soo.md", "sites/*/as-built.md", "followups/*.md"):
        docs.extend(sorted(vault.glob(pattern)))
    q = tokens(question)
    if not q:
        return 0.0, None, ""
    best = (0.0, None, "")
    for p in docs:
        text = p.read_text(encoding="utf-8")
        score = len(q & tokens(text)) / len(q)
        # A compounded known fix is the most specific answer for a repeat case:
        # give it priority over a general SOO line, but only when it really matches.
        if p.name == "known-fixes.md" and score >= 0.5:
            score = min(1.1, score + 0.3)
        if score > best[0]:
            best = (score, p, text)
    return best


def grounded_answer(vault, question):
    score, path, text = search_docs(vault, question)
    if path is None or score < 0.30:
        return (
            "NOT IN DOCS: this question is not covered by the sample docs. "
            "No step is invented. Escalate to the sample site lead and "
            "record it as a new follow-up with its source question."
        )
    # Return the most relevant line(s) from the matched doc, with citation.
    q = tokens(question)
    lines = []
    for line in text.splitlines():
        if len(q & tokens(line)) >= 2:
            lines.append(line.strip())
    snippet = " ".join(lines[:3]) if lines else text.splitlines()[0] if text else ""
    if path.name == "known-fixes.md":
        # Prepend the matching KF section header so a repeat case cites the fix id.
        best_section, best_score = "", 0
        for section in text.split("## "):
            s = len(q & tokens(section))
            if s > best_score:
                best_section, best_score = section, s
        header = best_section.splitlines()[0].strip() if best_section else ""
        if header:
            snippet = f"{header}: {snippet}"
    return f"Grounded answer, cited from {path.name} ({path.parent.name}): {snippet}"


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
