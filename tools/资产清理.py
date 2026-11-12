"""Plan or apply reference-safe removal of unused byte-identical asset images."""

import argparse
import json
from pathlib import Path

from autodl_video.asset_cleanup import apply_cleanup, write_plan

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "apply"])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    if args.action == "plan":
        result = write_plan(ROOT, args.plan)
    else:
        if args.journal is None:
            parser.error("apply requires --journal")
        result = apply_cleanup(
            json.loads(args.plan.read_text("utf-8")), root=ROOT, journal=args.journal
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
