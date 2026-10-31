"""Stable T-03 CLI; no model or conversation runtime."""
import argparse
import json
from pathlib import Path

from ._files import PackageError
from .doctor import check_character, check_current, check_instance
from .instances import create_instance


def main(argv=None):
    parser = argparse.ArgumentParser(prog="neurocore")
    sub = parser.add_subparsers(dest="command", required=True)
    new = sub.add_parser("new", help="Create a fresh identity from a local character package")
    new.add_argument("--character", required=True, help="Character package directory")
    new.add_argument("--instance", help="New instance directory (default: ./instances/<new UUID>)")
    doctor = sub.add_parser("doctor", help="Inspect files read-only; never repair or connect to models")
    target = doctor.add_mutually_exclusive_group()
    target.add_argument("--character", help="Inspect a character package")
    target.add_argument("--instance", help="Inspect an instance")
    args = parser.parse_args(argv)
    if args.command == "new":
        try:
            instance = create_instance(args.character, args.instance)
        except PackageError as exc:
            print(f"FAIL new: {exc}")
            return 1
        print(json.dumps({"instance_id": instance.instance_id,
                          "instance_directory": str(instance.root)}, ensure_ascii=True))
        return 0
    checks = (check_character(args.character) if args.character else
              check_instance(args.instance) if args.instance else check_current(Path.cwd()))
    for check in checks:
        print(f"{check.status} {check.name}: {check.message}")
    return int(any(check.status == "FAIL" for check in checks))
