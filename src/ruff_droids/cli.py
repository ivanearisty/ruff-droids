"""CLI entry point for ruff-droids."""

import argparse
import os
import sys
from pathlib import Path

from .orchestrator import run_lint_fix


def main() -> None:
    """Parse arguments, set up Factory auth, and delegate to the orchestrator."""
    try:
        _run()
    except KeyboardInterrupt:
        print("\n[ruff-droids] Interrupted. Exiting.")
        sys.exit(130)


def _run() -> None:
    parser = argparse.ArgumentParser(
        prog="ruff-droids",
        description="Run ruff auto-fixes and delegate remaining lint issues to Factory AI droids.",
    )
    parser.add_argument("--path", default=".", help="Target directory (default: .)")
    parser.add_argument("--factory-api-key", help="Factory API key (fallback: FACTORY_API_KEY env var)")
    parser.add_argument("--concurrency", type=int, default=4, help="Number of parallel droid-exec workers (default: 4)")
    args = parser.parse_args()

    target = str(Path(args.path).resolve())

    # 1) Set Factory auth
    api_key: str | None = args.factory_api_key or os.getenv("FACTORY_API_KEY")
    if not api_key:
        api_key = input("Enter your Factory API key: ").strip()
        if not api_key:
            print("Error: Factory API key is required.")
            sys.exit(1)
    os.environ["FACTORY_API_KEY"] = api_key

    # 2) Delegate to orchestrator
    sys.exit(run_lint_fix(target, concurrency=args.concurrency))
