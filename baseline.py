#!/usr/bin/env python3
"""
Measured baseline: grounded (files) vs model-alone (Token Factory, if a key is set).

Sample tickets, with expected ground truth, defined in tickets.json next to this file.
Grounded scoring is a deterministic citation/keyword check on continuity.grounded_answer.
Model-alone scoring, ONLY if NEBIUS_TOKEN_FACTORY_API_KEY is set, calls Nemotron
with no files and checks the same keywords. If no key is set, model-alone is
reported as SKIPPED, not invented, and the comparison is reported INCONCLUSIVE.

Tiny sample warning: this is a 5-ticket demo baseline, not a benchmark.
Do not quote it as a general accuracy claim.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from continuity import grounded_answer, MODEL, API_URL, vault_dir  # noqa: E402

ROOT = Path(__file__).resolve().parent


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


def score_grounded(answer, ticket):
    if not ticket["covered"]:
        return "not in docs" in answer.lower()
    return ticket["expected_keyword"].lower() in answer.lower()


def score_model_alone(answer, ticket):
    if answer is None:
        return None
    if not ticket["covered"]:
        # Invented if it gives a step instead of saying it does not know.
        low = answer.lower()
        return ("not in docs" in low or "don't know" in low or "do not know" in low)
    return ticket["expected_keyword"].lower() in answer.lower()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault-dir", default=None)
    args = parser.parse_args()
    vault = Path(args.vault_dir) if args.vault_dir else ROOT / "vault"
    tickets = json.loads((ROOT / "tickets.json").read_text(encoding="utf-8"))
    grounded_ok = 0
    model_ok = 0
    model_run = 0
    print(f"Baseline: {len(tickets)} sample tickets, vault={vault}")
    print(f"Model: {MODEL}")
    print(f"Token Factory key present: {'yes' if os.environ.get('NEBIUS_TOKEN_FACTORY_API_KEY') else 'no'}")
    print("")
    for t in tickets:
        g = grounded_answer(vault, t["question"])
        gs = score_grounded(g, t)
        grounded_ok += int(gs)
        m = None
        ms = None
        try:
            m = model_alone_answer(t["question"])
        except Exception as e:  # noqa: BLE001
            print(f"{t['id']}: model-alone call failed: {type(e).__name__}")
        if m is not None:
            model_run += 1
            ms = score_model_alone(m, t)
            model_ok += int(ms)
        print(f"{t['id']} covered={t['covered']} grounded={'PASS' if gs else 'FAIL'} "
              f"model-alone={'SKIPPED' if ms is None else ('PASS' if ms else 'FAIL')}")
        print(f"  Q: {t['question']}")
        print(f"  Grounded: {g[:220]}")
        if m:
            print(f"  Model-alone: {m[:220]}")
    print("")
    print(f"Grounded: {grounded_ok}/{len(tickets)}")
    if model_run:
        print(f"Model-alone: {model_ok}/{model_run}")
        print(f"Difference (grounded minus model-alone): {grounded_ok - model_ok} on {len(tickets)} tickets")
    else:
        print("Model-alone: SKIPPED (no Token Factory key; no numbers invented)")
        print("Comparison: INCONCLUSIVE on this run - grounded counts only, tiny 5-ticket sample")
    print("Limitation: tiny sample, keyword scoring, not a benchmark. Do not generalise.")


if __name__ == "__main__":
    main()
