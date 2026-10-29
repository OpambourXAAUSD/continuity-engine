"""Tests for the 4 LOCKED pass criteria. All use temp copies of the sample seed.
No real data, no network, no API key required. Run: python3 -m unittest discover -s tests -v
"""
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from continuity import grounded_answer  # noqa: E402


def fresh_vault(tmp):
    vault = Path(tmp) / "vault"
    shutil.copytree(ROOT / "vault-seed", vault)
    return vault


def run_cli(vault, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "continuity.py"), "--vault-dir", str(vault), *args],
        capture_output=True, text=True, check=False,
    )


class TestLocked(unittest.TestCase):
    def test_a_restart_identical(self):
        """a. Kill/restart: checklist rebuilds identically from files, no chat history."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            r1 = run_cli(vault, "checklist")
            r2 = run_cli(vault, "checklist")
            self.assertEqual(r1.returncode, 0)
            self.assertEqual(r2.returncode, 0)
            h1 = hashlib.sha256(r1.stdout.encode()).hexdigest()
            h2 = hashlib.sha256(r2.stdout.encode()).hexdigest()
            self.assertEqual(h1, h2, "checklist output differed between runs")
            self.assertIn("F20", r1.stdout)
            self.assertIn("F21", r1.stdout)
            # No chat history file is read or required.
            self.assertFalse(list(vault.glob("chat*.md")))
            self.assertFalse(list(vault.glob("*history*")))

    def test_b_correction_updates_not_contradicts(self):
        """b. A changed fact in state.md updates the next pickup output."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            before = run_cli(vault, "pickup").stdout
            self.assertIn("Sample site north status: normal", before)
            state = vault / "state.md"
            state.write_text(
                state.read_text().replace(
                    "Sample site north status: normal",
                    "Sample site north status: maintenance window",
                ),
                encoding="utf-8",
            )
            after = run_cli(vault, "pickup").stdout
            self.assertIn("Sample site north status: maintenance window", after)
            self.assertNotIn("Sample site north status: normal", after)

    def test_c_verify_blocks_bad_close(self):
        """c. Evidence-free close is refused by code, file unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            before = (vault / "followups" / "F20.md").read_text()
            r = run_cli(vault, "followup", "--close", "F20")
            self.assertNotEqual(r.returncode, 0, "verify should refuse an evidence-free close")
            self.assertIn("REFUSED", r.stdout)
            after = (vault / "followups" / "F20.md").read_text()
            self.assertEqual(before, after, "F20 file must be unchanged after a refused close")
            self.assertIn("Status: open", after)

    def test_c_verify_allows_evidence_close_and_compounds(self):
        """Compounding proof: a close with evidence creates KF-F21 and is cited on repeat."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            r = run_cli(vault, "followup", "--close", "F21")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("Status: closed", (vault / "followups" / "F21.md").read_text())
            kf = (vault / "known-fixes.md").read_text()
            self.assertIn("KF-F21", kf)
            self.assertIn("Source: F21", kf)
            answer = grounded_answer(vault, "sample gateway is offline after a service restart, what is the first remote check?")
            self.assertIn("KF-F21", answer, "repeat case answer itself should cite the compounded known fix")

    def test_d_unknown_question_not_in_docs(self):
        """d. Unknown question gets 'not in docs', escalates, never invents a step."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            answer = grounded_answer(
                vault, "how do I replace the sample reactor coolant valve X9?"
            )
            self.assertIn("not in docs", answer.lower())
            self.assertIn("escalate", answer.lower())
            # Must not present a replacement procedure as an answer.
            self.assertNotIn("Step 1", answer)

    def test_demo_mode_does_not_claim_live_call(self):
        """Without a key, pickup must label itself DEMO MODE, not a live call."""
        with tempfile.TemporaryDirectory() as tmp:
            vault = fresh_vault(tmp)
            r = run_cli(vault, "pickup")
            self.assertIn("DEMO MODE", r.stdout)
            self.assertNotIn("Token Factory draft (", r.stdout)


if __name__ == "__main__":
    unittest.main()
