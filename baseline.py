#!/usr/bin/env python3
"""
Measured baseline, 20 invented sample tickets: grounded structured
retrieval vs a simple naive chunk baseline vs model-alone.

- Grounded: continuity.grounded_answer on a temp copy of vault-seed,
  with F21 closed first so KF-F21 exists for the repeat case (T6),
  and with the correction case (T16) applied by editing state.md.
- Naive chunk: all seed docs (before compounding, no KF-F21, no
  correction) joined and split into 200-character chunks, best
  keyword chunk returned, no structure, no citation enforcement,
  no NOT IN DOCS rule. It therefore answers uncovered questions
  with a closest chunk instead of refusing, which is scored FAIL.
- Model-alone: ONLY if NEBIUS_TOKEN_FACTORY_API_KEY is set, calls
  Nemotron with no files. If no key is set, reported SKIPPED, not
  invented, and the comparison is INCONCLUSIVE.

Limitation: tiny 20-ticket invented sample, keyword scoring,
not a benchmark. Do not quote it as a general accuracy claim.
Do not generalise beyond this sample.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from continuity import grounded_answer, MODEL, API_URL  # noqa: E402

ROOT = Path(__file__).resolve().parent
STOP = {"the", "and", "for", "with", "what", "how", "should", "after",
        "from", "that", "this", "sample", "first", "check", "does", "are",
        "is", "a", "an", "to", "of", "in", "on", "do", "i", "my"}


def toks(text):
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) >= 3 and w not in STOP}


def model_alone_answer(question):
    key = os.environ.get("NEBIUS_TOKEN_FACTORY_API_KEY", "").strip()
    if not key:
        return None
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Answer briefly from general knowledge only. Do not claim to have files."},
            {"role": "user", "content": question},
        ],
        "temperature": 0.2,
        "max_tokens": 200,
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL, data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def naive_chunk_answer(seed_vault, question):
    """Naive chunk RAG, no structure: join seed docs, 200-char chunks, best keyword chunk."""
    text = ""
    for p in sorted(seed_vault.rglob("*.md")):
        text += p.read_text(encoding="utf-8") + "\n"
    chunks = [text[i:i + 200] for i in range(0, len(text), 200)]
    q = toks(question)
    if not q:
        return ""
    best, best_score = "", 0.0
    for c in chunks:
        score = len(q & toks(c)) / len(q)
        if score > best_score:
            best, best_score = c, score
    return best.strip()


def score_answer(answer, ticket, strict_kf=False):
    if not ticket["covered"]:
        return "not in docs" in answer.lower()
    return ticket["expected_keyword"].lower() in answer.lower()


def main():
    tickets = json.loads((ROOT / "tickets.json").read_text(encoding="utf-8"))
    print(f"Baseline: {len(tickets)} sample tickets")
    print(f"Model: {MODEL}")
    print(f"Token Factory key present: {'yes' if os.environ.get('NEBIUS_TOKEN_FACTORY_API_KEY') else 'no'}")
    print("")
    with tempfile.TemporaryDirectory() as tmp:
        vault = Path(tmp) / "vault"
        shutil.copytree(ROOT / "vault-seed", vault)
        # Compounding setup: close F21 in the temp copy, so KF-F21 exists.
        r = subprocess.run([sys.executable, str(ROOT / "continuity.py"), "--vault-dir", str(vault),
                            "followup", "--close", "F21"], capture_output=True, text=True)
        print(f"Setup close F21: exit {r.returncode} - {r.stdout.strip()}")
        seed_vault = ROOT / "vault-seed"
        grounded_ok = naive_ok = model_ok = model_run = 0
        for t in tickets:
            # Correction setup, applied only for this ticket, then restored.
            restored = None
            if t.get("setup") == "correction":
                state = vault / "state.md"
                restored = state.read_text(encoding="utf-8")
                state.write_text(restored.replace("Sample site north status: normal",
                                                  "Sample site north status: maintenance window"),
                                 encoding="utf-8")
            g = grounded_answer(vault, t["question"])
            gs = score_answer(g, t)
            grounded_ok += int(gs)
            n = naive_chunk_answer(seed_vault, t["question"])
            ns = score_answer(n, t)
            naive_ok += int(ns)
            m = None
            ms = None
            try:
                m = model_alone_answer(t["question"])
            except Exception as e:  # noqa: BLE001
                print(f"{t['id']}: model-alone call failed: {type(e).__name__}")
            if m is not None:
                model_run += 1
                ms = score_answer(m, t)
                model_ok += int(ms)
            if restored is not None:
                (vault / "state.md").write_text(restored, encoding="utf-8")
            print(f"{t['id']} covered={t['covered']} grounded={'PASS' if gs else 'FAIL'} "
                  f"naive={'PASS' if ns else 'FAIL'} "
                  f"model-alone={'SKIPPED' if ms is None else ('PASS' if ms else 'FAIL')}")
            print(f"  Q: {t['question']}")
            print(f"  Grounded: {g[:240]}")
            print(f"  Naive: {n[:240]}")
            if m:
                print(f"  Model-alone: {m[:240]}")
        print("")
        print(f"Grounded structured: {grounded_ok}/{len(tickets)}")
        print(f"Naive chunk: {naive_ok}/{len(tickets)}")
        if model_run:
            print(f"Model-alone: {model_ok}/{model_run}")
            print(f"Difference grounded minus naive: {grounded_ok - naive_ok} on {len(tickets)} tickets")
        else:
            print("Model-alone: SKIPPED (no Token Factory key; no numbers invented)")
            print("Comparison vs model-alone: INCONCLUSIVE on this run - grounded and naive counts only")
        print("Limitation: tiny invented sample, keyword scoring, not a benchmark. Do not generalise.")


if __name__ == "__main__":
    main()
