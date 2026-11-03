# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml", "pymupdf", "openpyxl"]
# ///
"""audit-prep CLI: init a corpus root, scan a raw paper folder, run the reviewed plan, review, finalize.

The dependencies above are those of the sibling modules this entry point loads
(scan: pyyaml, pymupdf; docs: openpyxl), since uv reads only this header.
"""
import argparse
import sys
from pathlib import Path

import corpus
import fetch_common
import prepare
import review


def _corpus(args) -> corpus.Corpus:
    return corpus.find_root(args.folder, args.root)


def cmd_init(args) -> int:
    root = corpus.init_root(args.dir).root
    print(f"initialized corpus root {root}")
    return 0


def cmd_scan(args) -> int:
    _corpus(args)
    plan = prepare.scan_folder(args.folder, fetch_common.default_get_json)
    print((args.folder / prepare.PLAN_NAME).read_text())
    statements = args.folder / prepare.STATEMENTS
    if statements.is_file():
        print(f"--- {statements.name} ---\n{statements.read_text()}")
    else:
        print(f"no paper candidate in {plan['paper_id']}; {statements.name} not written")
    return 0


def cmd_run(args) -> int:
    m = prepare.run_prep(args.folder, _corpus(args), dry_run=args.dry_run)
    if args.dry_run:
        return 0
    for warning in m["warnings"]:
        print(f"warning: {warning}")
    if m["review"]["status"] != "ok":
        print(review.format_review(m["review"]), file=sys.stderr)
        return 1
    print(f"prepared {m['paper_id']}; {review.format_review(m['review'])}; run prep.py finalize")
    return 0


def cmd_finalize(args) -> int:
    folder, kind = prepare.locate(args.folder, _corpus(args))
    if kind != "prepared":
        raise corpus.CorpusError(f"{folder} has not been prepared yet; run `prep.py run` first")
    m = prepare.finalize(folder)
    print(f"finalized {folder}: {len(m['files'])} files hashed, folder is read-only")
    return 0


def cmd_review(args) -> int:
    folder, _ = prepare.locate(args.folder, _corpus(args))
    m, plan = prepare.load_prepared(folder)
    result = review.review_folder(m, plan)
    print(review.format_review(result))
    return 0 if result["status"] == "ok" else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="prep.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="create a corpus root marker and folders")
    init.add_argument("dir", type=Path)
    init.set_defaults(func=cmd_init)
    for name, func, helptext in [("scan", cmd_scan, "draft prep.yaml and statements.md"),
                                 ("run", cmd_run, "execute a reviewed prep.yaml"),
                                 ("review", cmd_review, "print open and accepted prep problems"),
                                 ("finalize", cmd_finalize, "hash, write README, make read-only")]:
        p = sub.add_parser(name, help=helptext)
        p.add_argument("folder", type=Path)
        p.add_argument("--root", type=Path, default=None, help="corpus root (default: nearest marker)")
        if name == "run":
            p.add_argument("--dry-run", action="store_true", help="print planned actions only")
        p.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except review.ReviewError as e:
        print(e, file=sys.stderr)
        return 1
    except (prepare.PlanError, corpus.CorpusError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
