#!/usr/bin/env python3
"""Reset the working vault from the pristine sample seed. No real data, ever."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    seed = ROOT / "vault-seed"
    vault = ROOT / "vault"
    if vault.exists():
        shutil.rmtree(vault)
    shutil.copytree(seed, vault)
    print(f"Seeded {vault} from {seed}")

if __name__ == "__main__":
    main()
