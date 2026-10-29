# Continuity engine

**Headline: nothing drops when a person, a shift, or a day changes.**

A personal ledger that can be handed over, and that compounds into reusable
known fixes. Files are the truth. The model drafts. Code enforces.

Track: Personal AI (Nebius x NVIDIA Global AI Hackathon).
Built from Pickup mechanics, but not rigid to the name Pickup.

## The problem, for one specific user

Shift-based operations engineers drop follow-ups, repeat wrong first steps,
and lose context when a person, a shift, or a day changes. A generic
assistant guesses. In high-stakes work, a guessed field step wastes time
and erodes trust. This engine refuses to guess, cites the file it used,
and refuses to close a follow-up without evidence.

## The one-day loop: four commands only

```bash
python3 seed.py
python3 continuity.py pickup
python3 continuity.py checklist
python3 continuity.py followup
python3 continuity.py followup --close F20   # refused: no evidence
python3 continuity.py followup --close F21   # succeeds: evidence present, compounds to KF-F21
python3 continuity.py pickup --ask "sample gateway is offline after a service restart, what is the first remote check?"
python3 continuity.py pickup --ask "how do I replace the sample reactor coolant valve X9?"
python3 continuity.py wrapup
python3 seed.py   # reset to the clean sample vault
```

- `pickup`: morning hook, state, open follow-ups, today's checklist.
- `checklist`: write/update today's checklist from files. Re-running updates it.
- `followup`: bring all open F numbers to bear. `--close Fxx` attempts a close.
- `wrapup`: close the day, carry open items forward.

## Code-enforced verify, not a prompt

`followup --close Fxx` is refused by code, exit code 2, file unchanged, if
the F file's Evidence field is empty, `none`, `pending`, `tbc`, or `n/a`.
No prompt, no model, and no flag in this code can bypass that check.
A successful close appends a known-fix entry to `vault/known-fixes.md`,
with its source F id, problem, fix, and "do not" rule. A repeat sample
case then cites that KF entry, not just the general SOO.

## How Nemotron on Token Factory is used

- Model: `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`
- Endpoint: `https://api.tokenfactory.nebius.com/v1/chat/completions`
- In `continuity.py`, `token_factory_draft()` calls that endpoint when
  `NEBIUS_TOKEN_FACTORY_API_KEY` is set, passing file context and asking
  for a short morning summary draft, with an instruction not to invent
  facts. The file-generated checklist is always shown first; the model
  output is labelled separately, never presented as file truth.
- Why Nano fits an always-on cadence: it is the small, fast Nemotron
  variant, suited to frequent, low-cost drafts on a 2-hour cadence,
  where a large reasoning model on every check would be slow and
  expensive. Token Factory accelerated the workflow by providing a
  single public endpoint for that NVIDIA model, with a Playground
  test during setup. No other Nebius service is required for this build.

## Demo mode, stated honestly

If `NEBIUS_TOKEN_FACTORY_API_KEY` is not set, the app runs in clearly
labelled DEMO MODE: summaries are file-generated, and no live Token
Factory call is made or claimed. Tests and the demo flow work in demo
mode. A live Token Factory code call with a real key is still to be
proven by the author before submission, because the account balance
was $0.00 at setup and a promo code was rejected. Do not claim a live
call from a demo-mode run.

Set a key only via environment, never in a file or in chat:

```bash
export NEBIUS_TOKEN_FACTORY_API_KEY="your-key-here"
python3 continuity.py pickup
```

The key is read only from that variable, never printed, logged,
embedded, or stored by this code.

## Privacy boundary, stated exactly

- What stays in local files: the whole sample vault, contract, state,
  checklist, follow-ups, sample SOO, sample as-built, known fixes, wrapup.
- What is sent for a Token Factory call, only when a key is set: the
  file-generated checklist context (sample data only) and the draft
  request, to the endpoint above.
- What is never sent: credentials, API keys, real site names, real
  SOOs, real as-builts, customer data, or any work document. This build
  contains none of those, and makes no on-device or zero-retention
  claim, because neither is implemented here.

## Pre-existing explanation

This competition version is a NEW clean setup, created for this
hackathon. It contains no work laptop code, no work SOOs, no work
as-builts, no real site names, and no AWS internal data. All vault
content is invented sample data, clearly marked sample, for the demo
only. Any resemblance to a real site is coincidental and is not a
real site document.

## Tests: the 4 locked pass criteria

```bash
python3 -m unittest discover -s tests -v
```

- a. Restart identical: checklist run twice gives identical output, no chat history.
- b. Correction updates, not contradicts: editing `state.md` updates the next pickup output.
- c. Verify blocks a bad close: evidence-free close refused, file unchanged; evidence close succeeds and compounds.
- d. Unknown question: not covered by sample docs gives "not in docs" and escalates, never invents a step.

## Measured baseline

```bash
python3 baseline.py
```

Runs 5 sample tickets, grounded vs model-alone, with keyword/citation
scoring defined in `tickets.json`. If no Token Factory key is set,
model-alone is reported SKIPPED and the comparison INCONCLUSIVE, not
invented. The sample is tiny; it is not a benchmark, and must not be
quoted as a general accuracy claim.

## What is NOT in this build, on purpose

SAM 3.1, extra personas, voice, mobile app, real site data,
on-device/zero-retention claims, invented measurements.

## Still missing before submission (author to do, not done here)

- Live Token Factory code call with a real key, and a hosted demo URL.
- Demo video, 3 minutes or less, per DEMO-STORYBOARD.md.
- Public repo publish with this MIT LICENSE at the top.
- Devpost submission, description, and tools feedback, only with the author's say so.
