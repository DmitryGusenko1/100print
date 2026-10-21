#!/usr/bin/env python3
"""Show progress, or report an explicit task stage from the executor."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.progress import Progress, STAGES, format_progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issue', type=int)
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--current')
    parser.add_argument('--action')
    parser.add_argument('--eta')
    args = parser.parse_args()
    progress = Progress()
    if any(value is not None for value in (args.stage, args.current, args.action, args.eta)):
        if args.issue is None:
            parser.error('--issue is required for updates')
        try:
            state = progress.update(args.issue, args.stage, args.current, args.action, args.eta)
        except ValueError as error:
            parser.error(str(error))
    else:
        state = progress.read()
    print(format_progress(state))


if __name__ == '__main__':
    main()
