# Demo storyboard: 3 minutes or less

Total: 2:20 of scripted beats, with 40 seconds of buffer. Do not exceed 3:00.
Show the screen, do not just talk about the system. No video has been recorded yet.

## 0:00-0:20 Pitch + file tree
- Say: "Nothing drops when a person, a shift, or a day changes."
- Show the file tree: contract.md, state.md, checklist.md, followups/F20, F21,
  sites/sample-site-north/soo.md and as-built.md, known-fixes.md, wrapup.md.
- Say: files are the truth, the model drafts, code enforces. All sample data.

## 0:20-0:50 Morning checklist
- Run: `python3 continuity.py pickup`
- Point to: state, open F20 and F21, today's checklist.
- Note demo mode vs live Token Factory call honestly: if no key, say demo mode.

## 0:50-1:30 Cadence + grounded troubleshooting
- Run: `python3 continuity.py followup`
- Ask a covered question: sample gateway offline after a service restart.
  Show the cited SOO answer, with its "do not power-cycle" rule.
- Ask an uncovered question: sample reactor coolant valve X9.
  Show "not in docs" and escalate, no invented step.
- Mention the 2-hour cadence in one line, time-compressed, labelled as such.

## 1:30-2:20 Restart + correction + measured result
- Restart: run `python3 continuity.py checklist` twice, show identical output.
- Correction: change one fact in state.md, run pickup again, show it updates, not contradicts.
- Verify: try `followup --close F20`, show REFUSED, file unchanged.
  Then close F21 with evidence, show KF-F21 in known-fixes.md, then ask the
  gateway question again and show it citing KF-F21.
- Measured result: show `python3 baseline.py` output as run, with its
  limitation stated. Do not invent a model-alone number if the key was absent.

## 2:20-3:00 Stack, repo/demo links, one next step
- Stack: Nemotron-3-Nano-30B-A3B on Nebius Token Factory, why Nano fits
  an always-on cadence, code-enforced verify, sample-only vault.
- Show: repo link, demo link, README. (Links to be added at publish time.)
- One next step: take this personal ledger to a team handover, so a resolved
  fix compounds for the next engineer, not just for one person.
- Close on the headline, no call to action beyond the submission links.
