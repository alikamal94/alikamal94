"""Command line: python -m tauro <command>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import settings


def cmd_render(args: argparse.Namespace) -> int:
    from .data.prices import get_provider
    from .render.renderer import Renderer
    from .schemas import Brief, Copy

    renderer = Renderer(get_provider(args.prices or settings.price_provider))
    for path in args.files:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        brief, copy = Brief.model_validate(data["brief"]), Copy.model_validate(data["copy"])
        for png in renderer.render(brief, copy, Path(args.out)):
            print(png)
    return 0


def cmd_qa_check(args: argparse.Namespace) -> int:
    from .qa_rules import hard_checks
    from .schemas import Brief, Copy

    failed = False
    for path in args.files:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        problems = hard_checks(Brief.model_validate(data["brief"]), Copy.model_validate(data["copy"]))
        print(f"{path}: {'PASS' if not problems else 'FAIL'}")
        for p in problems:
            print(f"  - {p}")
        failed |= bool(problems)
    return 1 if failed else 0


def cmd_run(args: argparse.Namespace) -> int:
    from .orchestrator import Orchestrator

    Orchestrator.from_settings().run_batch(args.batch)
    return 0


def cmd_schedule(args: argparse.Namespace) -> int:
    from .orchestrator import Orchestrator

    Orchestrator.from_settings().run_forever()
    return 0


def cmd_bot(args: argparse.Namespace) -> int:
    from .telegram_bot import main as bot_main

    bot_main()
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    from .storage import Store

    store = Store(settings.db_path)
    store.set_flag("kill_switch", "off" if args.off else "on")
    print(f"kill switch {'OFF — publishing allowed' if args.off else 'ON — all publishing paused'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tauro")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render", help="render brief+copy JSON files to PNG")
    r.add_argument("files", nargs="+")
    r.add_argument("--out", default=str(settings.out_dir / "renders"))
    r.add_argument("--prices", choices=["sample", "mt5"])
    r.set_defaults(fn=cmd_render)
    q = sub.add_parser("qa-check", help="run the code-level QA rules on brief+copy JSON files")
    q.add_argument("files", nargs="+")
    q.set_defaults(fn=cmd_qa_check)
    b = sub.add_parser("run", help="run one batch now: morning | afternoon")
    b.add_argument("batch", choices=["morning", "afternoon"])
    b.set_defaults(fn=cmd_run)
    s = sub.add_parser("schedule", help="run the daily schedule (Kuwait time) until stopped")
    s.set_defaults(fn=cmd_schedule)
    t = sub.add_parser("bot", help="run the Telegram approval bot")
    t.set_defaults(fn=cmd_bot)
    k = sub.add_parser("kill", help="pause all publishing (use --off to resume)")
    k.add_argument("--off", action="store_true")
    k.set_defaults(fn=cmd_kill)
    args = ap.parse_args(argv)
    import logging

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
