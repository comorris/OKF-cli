from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from okf_cli.errors import ConfigurationError
from okf_cli.pi_archive import inventory_archive, iter_session_text


def _outside_bundle(output: Path, bundle: Path) -> bool:
    output = output.resolve(strict=False)
    bundle = bundle.resolve()
    return output != bundle and bundle not in output.parents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream filtered Pi JSONL sessions from a ZIP archive.")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-record-bytes", type=int, default=2 * 1024 * 1024)
    return parser


def run(args: argparse.Namespace) -> None:
    archive = args.archive.expanduser().resolve()
    bundle = args.bundle.expanduser().resolve()
    output = args.out.expanduser().resolve(strict=False)
    if not bundle.is_dir():
        raise ConfigurationError(f"bundle does not exist: {bundle}")
    if not _outside_bundle(output, bundle):
        raise ConfigurationError("archive output must be outside the bundle")
    if args.max_record_bytes <= 0:
        raise ConfigurationError("max-record-bytes must be positive")

    members = inventory_archive(archive)
    output.mkdir(parents=True, exist_ok=False)
    inventory = {
        "archive": str(archive),
        "members": [asdict(member) for member in members],
    }
    (output / "inventory.json").write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    with (output / "sessions.jsonl").open("w", encoding="utf-8") as stream:
        for session in iter_session_text(archive, max_record_bytes=args.max_record_bytes):
            stream.write(json.dumps(asdict(session), sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    try:
        run(build_parser().parse_args(argv))
    except ConfigurationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 6
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
