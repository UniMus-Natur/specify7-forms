"""specli entry point: `specli form|schema|weblink|formatter …`."""

from __future__ import annotations

import argparse
import sys

from specli.runner import load_repo_dotenv, run_script


def _add_form_commands(sub: argparse._SubParsersAction) -> None:
    form = sub.add_parser("form", help="Form/view XML sync (viewsets)")
    cmd = form.add_subparsers(dest="cmd", required=True)

    export = cmd.add_parser("export", help="Export forms from Specify to files")
    export.add_argument("--output-dir", default="forms", help="Output directory")
    export.add_argument("--collection", default=None, help="Collection name")
    export.add_argument("--clean", action="store_true", help="Delete output dir before writing")
    export.add_argument("--only-overrides", action="store_true", help="Write only overrides")
    export.add_argument("--no-manifests", action="store_true", help="Skip per-form manifest.json")

    plan = cmd.add_parser("plan", help="Dry-run form import (no writes)")
    plan.add_argument("--forms-dir", default="forms", help="Forms directory")
    plan.add_argument("--collection", default=None, help="Collection name")
    plan.add_argument("--viewset-name", default=None, help="Target viewset name")
    plan.add_argument("--verbose-missing", action="store_true", help="Print every missing mapping")
    plan.add_argument(
        "--source-mode",
        choices=("auto", "defaults", "overrides"),
        default="auto",
    )
    plan.add_argument(
        "--create-missing-views",
        action="store_true",
        help="Create missing <view> entries in target viewset",
    )

    imp = cmd.add_parser("import", help="Import forms into Specify")
    imp.add_argument("--forms-dir", default="forms", help="Forms directory")
    imp.add_argument("--collection", default=None, help="Collection name")
    imp.add_argument("--viewset-name", default=None, help="Target viewset name")
    imp.add_argument("--backup", default=None, help="Backup remote viewset XML before apply")
    imp.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    imp.add_argument("--verbose-missing", action="store_true", help="Print every missing mapping")
    imp.add_argument(
        "--source-mode",
        choices=("auto", "defaults", "overrides"),
        default="auto",
    )
    imp.add_argument(
        "--create-missing-views",
        action="store_true",
        help="Create missing <view> entries in target viewset",
    )


def _add_weblink_commands(sub: argparse._SubParsersAction) -> None:
    weblink = sub.add_parser("weblink", help="WebLink app-resource sync (WebLinks XML)")
    cmd = weblink.add_subparsers(dest="cmd", required=True)

    plan = cmd.add_parser("plan", help="Dry-run WebLink merge (no writes)")
    plan.add_argument("--collection", default=None, help="Specify collection to log into")
    plan.add_argument(
        "--asset-collection",
        default=None,
        help="Asset-server collection (default: SPECIFY7_ASSET_COLLECTION or NHM-karplanter)",
    )

    imp = cmd.add_parser("import", help="Merge WebLinks into Specify")
    imp.add_argument("--collection", default=None, help="Specify collection to log into")
    imp.add_argument(
        "--asset-collection",
        default=None,
        help="Asset-server collection (default: SPECIFY7_ASSET_COLLECTION or NHM-karplanter)",
    )
    imp.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")


def _add_formatter_commands(sub: argparse._SubParsersAction) -> None:
    formatter = sub.add_parser(
        "formatter",
        help="UI field formatter sync (UIFormatters XML)",
    )
    cmd = formatter.add_subparsers(dest="cmd", required=True)

    plan = cmd.add_parser("plan", help="Dry-run UIFormatter upsert (no writes)")
    plan.add_argument("--collection", default=None, help="Specify collection to log into")

    imp = cmd.add_parser("import", help="Upsert UIFormatters into Specify")
    imp.add_argument("--collection", default=None, help="Specify collection to log into")
    imp.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")


def _add_schema_commands(sub: argparse._SubParsersAction) -> None:
    schema = sub.add_parser("schema", help="Schema config sync (field visibility, labels)")
    cmd = schema.add_subparsers(dest="cmd", required=True)

    export = cmd.add_parser("export", help="Export schema config to JSON")
    export.add_argument("--output-dir", default="schema", help="Output directory")
    export.add_argument("--collection", default=None, help="Collection name")
    export.add_argument("--lang", default="en", help="Schema language (default: en)")
    export.add_argument("--clean", action="store_true", help="Delete output dir before writing")
    export.add_argument(
        "--split-tables",
        action="store_true",
        help="Also write per-table JSON under tables/",
    )
    export.add_argument(
        "--only-tables",
        default=None,
        help="Comma-separated table names to export",
    )

    plan = cmd.add_parser("plan", help="Dry-run schema import (no writes)")
    plan.add_argument("--schema-dir", default="schema", help="Schema directory")
    plan.add_argument("--collection", default=None, help="Collection name")
    plan.add_argument("--only-tables", default=None, help="Comma-separated table names")
    plan.add_argument("--verbose-missing", action="store_true", help="Print missing rows")
    plan.add_argument(
        "--create-missing",
        action="store_true",
        help="Create missing SpLocaleContainer / items",
    )

    imp = cmd.add_parser("import", help="Import schema JSON into Specify")
    imp.add_argument("--schema-dir", default="schema", help="Schema directory")
    imp.add_argument("--collection", default=None, help="Collection name")
    imp.add_argument("--only-tables", default=None, help="Comma-separated table names")
    imp.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    imp.add_argument("--verbose-missing", action="store_true", help="Print missing rows")
    imp.add_argument(
        "--create-missing",
        action="store_true",
        help="Create missing SpLocaleContainer / items",
    )


def _dispatch_form(args: argparse.Namespace) -> None:
    if args.cmd == "export":
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

    if args.cmd == "plan":
        run_script("import_specify_forms", argv)
        return

    if args.cmd == "import":
        if args.backup:
            argv += ["--backup", args.backup]
        if args.apply:
            argv += ["--apply"]
        run_script("import_specify_forms", argv)
        return


def _dispatch_weblink(args: argparse.Namespace) -> None:
    argv: list[str] = []
    if getattr(args, "collection", None):
        argv += ["--collection", args.collection]
    if getattr(args, "asset_collection", None):
        argv += ["--asset-collection", args.asset_collection]
    if args.cmd == "plan":
        run_script("import_specify_weblinks", argv)
        return
    if args.cmd == "import":
        if args.apply:
            argv += ["--apply"]
        run_script("import_specify_weblinks", argv)
        return


def _dispatch_formatter(args: argparse.Namespace) -> None:
    argv: list[str] = []
    if getattr(args, "collection", None):
        argv += ["--collection", args.collection]
    if args.cmd == "plan":
        run_script("import_specify_formatters", argv)
        return
    if args.cmd == "import":
        if args.apply:
            argv += ["--apply"]
        run_script("import_specify_formatters", argv)
        return


def _dispatch_schema(args: argparse.Namespace) -> None:
    if args.cmd == "export":
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

    if args.cmd == "plan":
        run_script("import_specify_schema", argv)
        return

    if args.cmd == "import":
        if args.apply:
            argv += ["--apply"]
        run_script("import_specify_schema", argv)
        return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="specli",
        description=(
            "Specify 7 GitOps CLI — forms, schema, WebLinks, and UI field formatters"
        ),
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
