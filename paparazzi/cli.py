"""Command-line entry point for paparazzi."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paparazzi import config


def is_anonymous(slug: str) -> bool:
    """True when a roster slug looks like an anonymous/stealth model."""
    return slug.startswith("stealth/") or "anon" in slug


def _print_missing(module: str, error: BaseException) -> None:
    print(f"paparazzi.{module} is not wired up yet: {error}")


def _close(conn) -> None:
    try:
        if conn is not None:
            conn.close()
    except Exception:
        pass


def _print_failed_run(conn, slug: str) -> None:
    """Show the failure that a run row recorded, instead of dying silently."""
    try:
        row = conn.execute(
            "SELECT error FROM probe_runs WHERE slug = ? AND ok = 0 ORDER BY id DESC LIMIT 1",
            (slug,),
        ).fetchone()
    except Exception:
        row = None
    error = None if row is None else row["error"]
    print(f"probe run failed: {error or 'no error recorded'}")


def _cmd_know(args: argparse.Namespace) -> int:
    try:
        from paparazzi import probe
    except Exception as error:
        _print_missing("probe", error)
        return 1

    from paparazzi import db

    conn = db.connect(config.db_path())
    mock = bool(args.mock) or config.mock()
    try:
        result = probe.know(args.slug, mock=mock, conn=conn)
    except SystemExit as error:
        _print_failed_run(conn, args.slug)
        _close(conn)
        return int(error.code or 1)
    except Exception as error:
        print(f"paparazzi.probe failed: {error}")
        _close(conn)
        return 1
    _close(conn)

    families = ", ".join(result.get("families", [])) or "none"
    source = "fixture replay" if mock else "live calls"
    print(f"signature stored for {args.slug} from {source}: {families}")
    return 0


def _cmd_watch(args: argparse.Namespace) -> int:
    try:
        from paparazzi import openrouter
    except Exception as error:
        _print_missing("openrouter", error)
        return 1

    from paparazzi import db

    conn = db.connect(config.db_path())
    mock = bool(args.mock) or config.mock()
    try:
        try:
            roster = openrouter.models(mock=mock)
        except TypeError:
            roster = openrouter.models()
    except Exception as error:
        print(f"paparazzi.openrouter failed: {error}")
        _close(conn)
        return 1

    slugs: list[str] = []
    for entry in roster or []:
        if isinstance(entry, str):
            slugs.append(entry)
            continue
        if not isinstance(entry, dict):
            continue
        slug = (
            entry.get("id")
            or entry.get("slug")
            or entry.get("canonical_slug")
            or entry.get("name")
        )
        if slug is not None:
            slugs.append(str(slug))

    # An empty roster means the fetch failed, not that every model left.
    # Marking models gone off a failed call would put a lie in the table.
    if not slugs:
        if mock:
            print("mock roster is empty, nothing to diff")
            _close(conn)
            return 0
        print("no roster fetched, so nothing was marked gone")
        _close(conn)
        return 1

    active_rows = db.list_models(conn, status="active")
    active_slugs = {str(row["slug"]) for row in active_rows}
    roster_set = set(slugs)

    for slug in slugs:
        db.upsert_model(conn, slug, anonymous=is_anonymous(slug), status="active")

    gone = sorted(active_slugs - roster_set)
    for slug in gone:
        db.mark_model_gone(conn, slug)

    new_slugs = [slug for slug in slugs if slug not in active_slugs]
    new_stealth = [slug for slug in new_slugs if is_anonymous(slug)]

    print("New stealth slugs: " + (", ".join(new_stealth) if new_stealth else "none"))
    print("Rotated off: " + (", ".join(gone) if gone else "none"))

    _close(conn)
    return 0


def _cmd_probe(args: argparse.Namespace) -> int:
    try:
        from paparazzi import probe
    except Exception as error:
        _print_missing("probe", error)
        return 1

    from paparazzi import db

    conn = db.connect(config.db_path())
    mock = bool(args.mock) or config.mock()
    try:
        run_ids = probe.run_all(args.slug, conn=conn, mock=mock)
    except SystemExit as error:
        _print_failed_run(conn, args.slug)
        _close(conn)
        return int(error.code or 1)
    except Exception as error:
        print(f"paparazzi.probe failed: {error}")
        _close(conn)
        return 1
    _close(conn)

    source = "fixture replay" if mock else "live calls"
    print(f"probed {args.slug} from {source}: {', '.join(run_ids)}")
    return 0


def _cmd_match(args: argparse.Namespace) -> int:
    try:
        from paparazzi import match
    except Exception as error:
        _print_missing("match", error)
        return 1

    from paparazzi import db

    conn = db.connect(config.db_path())
    try:
        report = match.evaluate(args.slug, conn=conn)
    except SystemExit as error:
        _print_failed_run(conn, args.slug)
        _close(conn)
        return int(error.code or 1)
    except Exception as error:
        print(f"paparazzi.match failed: {error}")
        _close(conn)
        return 1
    _close(conn)

    if not isinstance(report, dict) or not report.get("best"):
        print("no guess: no measured signals or no stored signatures to compare against")
        return 0

    # evaluate() already stored the guess row, so this only reports it.
    print(f"guess: {report['best']} ({report['score']})")
    if report.get("used_mock"):
        print("runs were fixture replays, so this guess is not publishable")
    if report.get("met_bar"):
        print("meets the publish bar, waiting for a human to approve")
    else:
        print("low confidence, not published as guess")
    return 0


def _cmd_reveal(args: argparse.Namespace) -> int:
    from paparazzi import db

    conn = db.connect(config.db_path())
    try:
        guess = db.latest_guess(conn, args.slug)
        our_guess = None if guess is None else str(guess["candidate"])
        hit = db.set_reveal(conn, args.slug, args.true_name, args.source_url)
    except Exception as error:
        print(f"reveal failed: {error}")
        _close(conn)
        return 1
    _close(conn)
    label = "hit" if hit else "miss"
    if our_guess is None:
        print(f"{label}: no prior guess on file")
    else:
        print(f"{label}: guessed {our_guess}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    try:
        from paparazzi import report
    except Exception as error:
        _print_missing("report", error)
        return 1
    try:
        report.write()
    except Exception as error:
        print(f"paparazzi.report failed: {error}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paparazzi")
    subparsers = parser.add_subparsers(dest="command", required=True)

    know = subparsers.add_parser("know")
    know.add_argument("slug")
    know.add_argument("--mock", action="store_true")
    know.set_defaults(handler=_cmd_know)

    watch = subparsers.add_parser("watch")
    watch.add_argument("--mock", action="store_true")
    watch.set_defaults(handler=_cmd_watch)

    probe = subparsers.add_parser("probe")
    probe.add_argument("slug")
    probe.add_argument("--mock", action="store_true")
    probe.set_defaults(handler=_cmd_probe)

    match = subparsers.add_parser("match")
    match.add_argument("slug")
    match.add_argument("--mock", action="store_true")
    match.set_defaults(handler=_cmd_match)

    reveal = subparsers.add_parser("reveal")
    reveal.add_argument("slug")
    reveal.add_argument("true_name")
    reveal.add_argument("source_url")
    reveal.set_defaults(handler=_cmd_reveal)

    report = subparsers.add_parser("report")
    report.set_defaults(handler=_cmd_report)

    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code) if error.code is not None else 0

    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 2
    return int(handler(args))