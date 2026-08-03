"""specli entry point: `specli form|schema|weblink|formatter pull|push|status …`.

Git-style verbs (remote = Specify instance, local = this repo):

  pull    Specify → git   (was: export)
  push    git → Specify   (was: import --apply)
  status  dry-run push    (was: plan / import without --apply)

Legacy aliases ``export`` / ``import`` / ``plan`` still work.
"""

from __future__ import annotations

import argparse
import sys

from specli.runner import load_repo_dotenv, run_script


def _add_form_commands(sub: argparse._SubParsersAction) -> None:
    form = sub.add_parser("form", help="Form/view XML sync (viewsets)")
    cmd = form.add_subparsers(dest="cmd", required=True)

    pull = cmd.add_parser(
        "pull",
        aliases=("export",),
        help="Pull forms from Specify into local files (Specify → git)",
    )
    pull.add_argument("--output-dir", default="forms", help="Output directory")
    pull.add_argument("--collection", default=None, help="Collection name")
    pull.add_argument("--clean", action="store_true", help="Delete output dir before writing")
    pull.add_argument("--only-overrides", action="store_true", help="Write only overrides")
    pull.add_argument("--no-manifests", action="store_true", help="Skip per-form manifest.json")

    def _add_form_push_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--forms-dir", default="forms", help="Forms directory")
        p.add_argument("--collection", default=None, help="Collection name")
        p.add_argument("--viewset-name", default=None, help="Target viewset name")
        p.add_argument("--verbose-missing", action="store_true", help="Print every missing mapping")
        p.add_argument(
            "--source-mode",
            choices=("auto", "defaults", "overrides"),
            default="auto",
        )
        p.add_argument(
            "--create-missing-views",
            action="store_true",
            help="Create missing <view> entries in target viewset",
        )
        p.add_argument("--backup", default=None, help="Backup remote viewset XML before push")

    push = cmd.add_parser(
        "push",
        aliases=("import",),
        help="Push local forms to Specify (git → Specify)",
    )
    _add_form_push_args(push)
    push.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing (same as status)",
    )
    # Legacy: import required --apply; keep it as a no-op so old scripts still work
    push.add_argument(
        "--apply",
        action="store_true",
        help=argparse.SUPPRESS,
    )

    status = cmd.add_parser(
        "status",
        aliases=("plan",),
        help="Dry-run: what would push change on Specify",
    )
    _add_form_push_args(status)


def _add_schema_commands(sub: argparse._SubParsersAction) -> None:
    schema = sub.add_parser("schema", help="Schema config sync (field visibility, labels)")
    cmd = schema.add_subparsers(dest="cmd", required=True)

    pull = cmd.add_parser(
        "pull",
        aliases=("export",),
        help="Pull schema config from Specify into local JSON (Specify → git)",
    )
    pull.add_argument("--output-dir", default="schema", help="Output directory")
    pull.add_argument("--collection", default=None, help="Collection name")
    pull.add_argument("--lang", default="en", help="Schema language (default: en)")
    pull.add_argument("--clean", action="store_true", help="Delete output dir before writing")
    pull.add_argument(
        "--split-tables",
        action="store_true",
        help="Also write per-table JSON under tables/",
    )
    pull.add_argument(
        "--only-tables",
        default=None,
        help="Comma-separated table names to pull",
    )

    def _add_schema_push_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--schema-dir", default="schema", help="Schema directory")
        p.add_argument("--collection", default=None, help="Collection name")
        p.add_argument("--only-tables", default=None, help="Comma-separated table names")
        p.add_argument("--verbose-missing", action="store_true", help="Print missing rows")
        p.add_argument(
            "--create-missing",
            action="store_true",
            help="Create missing SpLocaleContainer / items",
        )

    push = cmd.add_parser(
        "push",
        aliases=("import",),
        help="Push local schema JSON to Specify (git → Specify)",
    )
    _add_schema_push_args(push)
    push.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing (same as status)",
    )
    push.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)

    status = cmd.add_parser(
        "status",
        aliases=("plan",),
        help="Dry-run: what would push change on Specify",
    )
    _add_schema_push_args(status)


def _add_weblink_commands(sub: argparse._SubParsersAction) -> None:
    weblink = sub.add_parser("weblink", help="WebLink app-resource sync (WebLinks XML)")
    cmd = weblink.add_subparsers(dest="cmd", required=True)

    def _add_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--collection", default=None, help="Specify collection to log into")
        p.add_argument(
            "--asset-collection",
            default=None,
            help="Asset-server collection (default: SPECIFY7_ASSET_COLLECTION or NHM-karplanter)",
        )

    push = cmd.add_parser(
        "push",
        aliases=("import",),
        help="Push local WebLink defs to Specify (git → Specify)",
    )
    _add_args(push)
    push.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing (same as status)",
    )
    push.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)

    status = cmd.add_parser(
        "status",
        aliases=("plan",),
        help="Dry-run: what would push change on Specify",
    )
    _add_args(status)


def _add_formatter_commands(sub: argparse._SubParsersAction) -> None:
    formatter = sub.add_parser(
        "formatter",
        help="UI field formatter sync (UIFormatters XML)",
    )
    cmd = formatter.add_subparsers(dest="cmd", required=True)

    push = cmd.add_parser(
        "push",
        aliases=("import",),
        help="Push local UIFormatters to Specify (git → Specify)",
    )
    push.add_argument("--collection", default=None, help="Specify collection to log into")
    push.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing (same as status)",
    )
    push.add_argument("--apply", action="store_true", help=argparse.SUPPRESS)

    status = cmd.add_parser(
        "status",
        aliases=("plan",),
        help="Dry-run: what would push change on Specify",
    )
    status.add_argument("--collection", default=None, help="Specify collection to log into")


def _normalize_cmd(cmd: str) -> str:
    """Map legacy verbs onto pull/push/status."""
    return {
        "export": "pull",
        "import": "push",
        "plan": "status",
    }.get(cmd, cmd)


def _dispatch_form(args: argparse.Namespace) -> None:
    raw_cmd = args.cmd
    cmd = _normalize_cmd(raw_cmd)

    if cmd == "pull":
        argv: list[str] = ["--output-dir", args.output_dir]
        if args.collection:
            argv += ["--collection", args.collection]
        if args.clean:
            argv += ["--clean"]
        if args.only_overrides:
            argv += ["--only-overrides"]
        if args.no_manifests:
            argv += ["--no-manifests"]
        run_script("export_specify_forms", argv)
        return

    argv = ["--forms-dir", args.forms_dir, "--source-mode", args.source_mode]
    if args.collection:
        argv += ["--collection", args.collection]
    if args.viewset_name:
        argv += ["--viewset-name", args.viewset_name]
    if args.verbose_missing:
        argv += ["--verbose-missing"]
    if args.create_missing_views:
        argv += ["--create-missing-views"]
    if getattr(args, "backup", None):
        argv += ["--backup", args.backup]

    if _is_dry_run(raw_cmd, args):
        run_script("import_specify_forms", argv)
        return

    argv += ["--apply"]
    run_script("import_specify_forms", argv)


def _is_dry_run(raw_cmd: str, args: argparse.Namespace) -> bool:
    """status/plan are always dry-run; push applies unless --dry-run.

    Legacy ``import`` still requires ``--apply`` to write (old scripts).
    """
    cmd = _normalize_cmd(raw_cmd)
    if cmd == "status":
        return True
    if getattr(args, "dry_run", False):
        return True
    if raw_cmd == "import" and not getattr(args, "apply", False):
        return True
    return False


def _dispatch_schema(args: argparse.Namespace) -> None:
    raw_cmd = args.cmd
    cmd = _normalize_cmd(raw_cmd)

    if cmd == "pull":
        argv = ["--output-dir", args.output_dir, "--lang", args.lang]
        if args.collection:
            argv += ["--collection", args.collection]
        if args.clean:
            argv += ["--clean"]
        if args.split_tables:
            argv += ["--split-tables"]
        if args.only_tables:
            argv += ["--only-tables", args.only_tables]
        run_script("export_specify_schema", argv)
        return

    argv = ["--schema-dir", args.schema_dir]
    if args.collection:
        argv += ["--collection", args.collection]
    if args.only_tables:
        argv += ["--only-tables", args.only_tables]
    if args.verbose_missing:
        argv += ["--verbose-missing"]
    if args.create_missing:
        argv += ["--create-missing"]

    if _is_dry_run(raw_cmd, args):
        run_script("import_specify_schema", argv)
        return

    argv += ["--apply"]
    run_script("import_specify_schema", argv)


def _dispatch_weblink(args: argparse.Namespace) -> None:
    raw_cmd = args.cmd
    argv: list[str] = []
    if getattr(args, "collection", None):
        argv += ["--collection", args.collection]
    if getattr(args, "asset_collection", None):
        argv += ["--asset-collection", args.asset_collection]

    if _is_dry_run(raw_cmd, args):
        run_script("import_specify_weblinks", argv)
        return

    argv += ["--apply"]
    run_script("import_specify_weblinks", argv)


def _dispatch_formatter(args: argparse.Namespace) -> None:
    raw_cmd = args.cmd
    argv: list[str] = []
    if getattr(args, "collection", None):
        argv += ["--collection", args.collection]

    if _is_dry_run(raw_cmd, args):
        run_script("import_specify_formatters", argv)
        return

    argv += ["--apply"]
    run_script("import_specify_formatters", argv)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="specli",
        description=(
            "Specify 7 GitOps CLI — pull/push forms, schema, WebLinks, and UIFormatters"
        ),
        epilog=(
            "Think git: pull = Specify→git, push = git→Specify, status = dry-run push. "
            "Legacy export/import/plan aliases still work."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__import__('specli').__version__}",
    )
    sub = parser.add_subparsers(dest="domain", required=True)
    _add_form_commands(sub)
    _add_schema_commands(sub)
    _add_weblink_commands(sub)
    _add_formatter_commands(sub)

    args = parser.parse_args(argv)
    load_repo_dotenv()

    if args.domain == "form":
        _dispatch_form(args)
    elif args.domain == "schema":
        _dispatch_schema(args)
    elif args.domain == "weblink":
        _dispatch_weblink(args)
    elif args.domain == "formatter":
        _dispatch_formatter(args)
    else:
        parser.error(f"unknown domain: {args.domain}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
