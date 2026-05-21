#!/usr/bin/env python3
"""Export Specify schema configuration (SpLocaleContainer) to git-friendly JSON.

Uses the same resolved shape as the Schema Configuration UI export:
  GET /context/schema_localization.json?lang=<lang>

Writes:
  <output-dir>/<discipline-slug>/meta.json
  <output-dir>/<discipline-slug>/schema.<lang>.json

Optional:
  --split-tables  -> also write tables/<table>.json per table (for smaller diffs)

Usage:
  python3 scripts/schema.py export --output-dir schema
  python3 scripts/export_specify_schema.py --output-dir schema --lang en
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from _specify_client import (
    disable_insecure_request_warnings,
    get_json,
    load_env_from_repo,
    login,
    require_env,
    resource_pk,
    safe_slug,
)


def _count_fields(schema: dict[str, Any]) -> tuple[int, int, int]:
    tables = 0
    fields = 0
    visible = 0
    for table_name, table_cfg in schema.items():
        if not isinstance(table_cfg, dict):
            continue
        tables += 1
        items = table_cfg.get("items") or {}
        if not isinstance(items, dict):
            continue
        for _fname, field_cfg in items.items():
            if not isinstance(field_cfg, dict):
                continue
            fields += 1
            if not field_cfg.get("ishidden"):
                visible += 1
    return tables, fields, visible


def main() -> None:
    disable_insecure_request_warnings()
    parser = argparse.ArgumentParser(description="Export Specify schema configuration to JSON")
    parser.add_argument("--output-dir", default="schema", help="Output directory (default: schema)")
    parser.add_argument(
        "--collection",
        default=os.getenv("SPECIFY7_COLLECTION"),
        help="Collection name for login (default: SPECIFY7_COLLECTION)",
    )
    parser.add_argument("--lang", default="en", help="Schema language tag (default: en)")
    parser.add_argument("--clean", action="store_true", help="Delete output dir before writing")
    parser.add_argument(
        "--split-tables",
        action="store_true",
        help="Also write per-table JSON under tables/ (optional, for focused diffs)",
    )
    parser.add_argument(
        "--only-tables",
        default=None,
        help="Comma-separated table names to export (lowercase datamodel names)",
    )
    args = parser.parse_args()

    load_env_from_repo()
    base = require_env("SPECIFY7_URL").rstrip("/")
    user = require_env("SPECIFY7_USER")
    password = require_env("SPECIFY7_PASSWORD")

    session, collection_name, collection_id = login(
        base, user, password, args.collection, log_prefix="export_specify_schema"
    )

    collection = get_json(session, base, f"/api/specify/collection/{collection_id}/")
    discipline_uri = collection.get("discipline")
    discipline_id = resource_pk(discipline_uri)
    if discipline_id is None:
        sys.exit("Could not resolve discipline from collection")

    discipline = get_json(session, base, f"/api/specify/discipline/{discipline_id}/")
    discipline_name = str(discipline.get("name") or f"discipline-{discipline_id}")
    discipline_type = str(discipline.get("type") or "unknown")
    slug = safe_slug(discipline_type) if discipline_type != "unknown" else safe_slug(discipline_name)

    lang = args.lang.strip().lower()
    schema = get_json(
        session,
        base,
        f"/context/schema_localization.json?lang={quote(lang)}",
    )
    if not isinstance(schema, dict):
        sys.exit("Unexpected schema_localization.json payload (expected object)")

    only_tables: set[str] | None = None
    if args.only_tables:
        only_tables = {t.strip().lower() for t in args.only_tables.split(",") if t.strip()}
        schema = {k: v for k, v in schema.items() if k.lower() in only_tables}

    output_dir = Path(args.output_dir)
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    discipline_dir = output_dir / slug
    discipline_dir.mkdir(parents=True, exist_ok=True)

    tables_n, fields_n, visible_n = _count_fields(schema)

    meta = {
        "discipline_id": discipline_id,
        "discipline_name": discipline_name,
        "discipline_type": discipline_type,
        "discipline_slug": slug,
        "collection_id": collection_id,
        "collection_name": collection_name,
        "language": lang,
        "source": base,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "table_count": tables_n,
        "field_count": fields_n,
        "visible_field_count": visible_n,
    }
    (discipline_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    schema_path = discipline_dir / f"schema.{lang}.json"
    schema_path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if args.split_tables:
        tables_dir = discipline_dir / "tables"
        tables_dir.mkdir(parents=True, exist_ok=True)
        for table_name in sorted(schema):
            table_cfg = schema[table_name]
            if isinstance(table_cfg, dict):
                (tables_dir / f"{table_name}.json").write_text(
                    json.dumps(table_cfg, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )

    summary = {
        "output": str(discipline_dir),
        "schema_file": str(schema_path.name),
        **meta,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        f"[export_specify_schema] done: discipline={discipline_name} ({slug}), "
        f"tables={tables_n}, fields={fields_n}, visible={visible_n}, output={discipline_dir}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
