#!/usr/bin/env python3
"""Import git-tracked schema JSON into Specify (SpLocaleContainer / items / labels).

Reads:
  <schema-dir>/<discipline-slug>/meta.json
  <schema-dir>/<discipline-slug>/schema.<lang>.json

Dry-run by default. Use --apply to write.

Usage:
  specli schema status --schema-dir schema
  specli schema push --schema-dir schema
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

from _specify_client import (
    disable_insecure_request_warnings,
    get_json,
    iter_list_endpoint,
    load_env_from_repo,
    login,
    post_json,
    put_json,
    require_env,
    resource_pk,
    strip_meta_for_put,
)


# Fields we sync from schema_localization.json onto API resources.
_ITEM_SYNC_KEYS = ("ishidden", "isrequired", "picklistname", "format", "weblinkname")
_CONTAINER_SYNC_KEYS = ("ishidden", "picklistname", "format", "aggregator", "defaultui")


def _norm_bool(value: Any) -> bool:
    return bool(value)


def _load_schema_bundle(schema_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    if not schema_dir.exists():
        sys.exit(f"Schema directory does not exist: {schema_dir}")

    meta_path = None
    for candidate in sorted(schema_dir.glob("*/meta.json")):
        meta_path = candidate
        break
    if meta_path is None:
        if (schema_dir / "meta.json").exists():
            bundle_dir = schema_dir
            meta_path = schema_dir / "meta.json"
        else:
            sys.exit(
                f"No discipline bundle found under {schema_dir} "
                "(expected <dir>/<slug>/meta.json)"
            )
    else:
        bundle_dir = meta_path.parent

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    lang = str(meta.get("language") or "en").strip().lower()
    schema_path = bundle_dir / f"schema.{lang}.json"
    if not schema_path.exists():
        found = sorted(bundle_dir.glob("schema.*.json"))
        if not found:
            sys.exit(f"No schema.<lang>.json found in {bundle_dir}")
        schema_path = found[0]
        lang = schema_path.stem.split(".", 1)[-1]

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(schema, dict):
        sys.exit(f"{schema_path}: expected JSON object at top level")

    meta = {**meta, "language": lang, "schema_file": schema_path.name}
    return bundle_dir, meta, schema


def _parse_lang(lang: str) -> tuple[str, str | None]:
    if "-" in lang:
        language, country = lang.lower().split("-", 1)
        return language, country or None
    return lang.lower(), None


def _locale_rows_for_item(
    session: requests.Session,
    base: str,
    item_id: int,
    *,
    name_key: str,
) -> list[dict[str, Any]]:
    return iter_list_endpoint(
        session,
        base,
        f"/api/specify/splocaleitemstr/?{name_key}={item_id}",
    )


def _sync_locale_string(
    session: requests.Session,
    base: str,
    *,
    item_id: int,
    name_key: str,
    language: str,
    country: str | None,
    text: str | None,
    dry_run: bool,
) -> bool:
    if text is None:
        return False
    text = str(text)
    rows = _locale_rows_for_item(session, base, item_id, name_key=name_key)
    match = None
    for row in rows:
        row_lang = str(row.get("language") or "").lower()
        row_country = row.get("country")
        if row_lang != language:
            continue
        if country is None:
            if row_country not in (None, ""):
                continue
        elif str(row_country or "").lower() != country:
            continue
        match = row
        break

    if match is not None:
        if str(match.get("text") or "") == text:
            return False
        if dry_run:
            return True
        rid = int(match["id"])
        full = get_json(session, base, f"/api/specify/splocaleitemstr/{rid}/")
        body = strip_meta_for_put(full)
        body["text"] = text
        put_json(session, base, f"/api/specify/splocaleitemstr/{rid}/", body)
        return True

    if dry_run:
        return True
    post_json(
        session,
        base,
        "/api/specify/splocaleitemstr/",
        {
            name_key: f"/api/specify/splocalecontaineritem/{item_id}/",
            "language": language,
            "country": country,
            "text": text,
        },
    )
    return True


def _item_patch_body(
    remote: dict[str, Any],
    desired: dict[str, Any],
) -> dict[str, Any] | None:
    body = strip_meta_for_put(remote)
    changed = False
    for key in _ITEM_SYNC_KEYS:
        if key not in desired:
            continue
        new_val = desired[key]
        if key in ("ishidden", "isrequired"):
            new_val = _norm_bool(new_val)
        if body.get(key) != new_val:
            body[key] = new_val
            changed = True
    return body if changed else None


def _container_patch_body(
    remote: dict[str, Any],
    desired: dict[str, Any],
) -> dict[str, Any] | None:
    body = strip_meta_for_put(remote)
    changed = False
    for key in _CONTAINER_SYNC_KEYS:
        if key not in desired:
            continue
        new_val = desired[key]
        if key == "ishidden":
            new_val = _norm_bool(new_val)
        if body.get(key) != new_val:
            body[key] = new_val
            changed = True
    return body if changed else None


def _index_items_by_name(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        name = str(item.get("name") or "").lower()
        if name:
            out[name] = item
    return out


def main() -> None:
    disable_insecure_request_warnings()
    parser = argparse.ArgumentParser(description="Import schema JSON into Specify")
    parser.add_argument("--schema-dir", default="schema", help="Schema directory")
    parser.add_argument(
        "--collection",
        default=os.getenv("SPECIFY7_COLLECTION"),
        help="Collection name for login",
    )
    parser.add_argument(
        "--only-tables",
        default=None,
        help="Comma-separated table names to import (lowercase)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default is dry-run)",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Create missing SpLocaleContainer / SpLocaleContainerItem rows",
    )
    parser.add_argument(
        "--verbose-missing",
        action="store_true",
        help="Print each table/field with no remote match",
    )
    args = parser.parse_args()

    load_env_from_repo()
    base = require_env("SPECIFY7_URL").rstrip("/")
    user = require_env("SPECIFY7_USER")
    password = require_env("SPECIFY7_PASSWORD")

    bundle_dir, meta, schema = _load_schema_bundle(Path(args.schema_dir))
    language, country = _parse_lang(str(meta.get("language") or "en"))

    session, collection_name, collection_id = login(
        base, user, password, args.collection, log_prefix="import_specify_schema"
    )

    collection = get_json(session, base, f"/api/specify/collection/{collection_id}/")
    live_discipline_id = resource_pk(collection.get("discipline"))
    meta_discipline_id = meta.get("discipline_id")
    if meta_discipline_id is not None and live_discipline_id != meta_discipline_id:
        print(
            f"[import_specify_schema] warning: meta discipline_id={meta_discipline_id} "
            f"!= login discipline_id={live_discipline_id} (using login context)",
            file=sys.stderr,
        )
    discipline_id = live_discipline_id or meta_discipline_id
    if discipline_id is None:
        sys.exit("Could not resolve discipline id")

    only_tables: set[str] | None = None
    if args.only_tables:
        only_tables = {t.strip().lower() for t in args.only_tables.split(",") if t.strip()}

    discipline_uri = f"/api/specify/discipline/{discipline_id}/"
    remote_containers = iter_list_endpoint(
        session,
        base,
        f"/api/specify/splocalecontainer/?discipline={discipline_id}&schematype=0",
    )
    remote_containers = [
        c
        for c in remote_containers
        if resource_pk(c.get("discipline")) == discipline_id
        or c.get("discipline") == discipline_uri
    ]
    containers_by_name = {
        str(c.get("name") or "").lower(): c
        for c in remote_containers
        if c.get("name")
    }

    stats = {
        "schema_dir": str(bundle_dir),
        "discipline_id": discipline_id,
        "collection_name": collection_name,
        "language": meta.get("language"),
        "dry_run": not args.apply,
        "tables_in_git": 0,
        "fields_in_git": 0,
        "containers_changed": 0,
        "items_changed": 0,
        "labels_changed": 0,
        "containers_missing": 0,
        "fields_missing": 0,
        "containers_created": 0,
        "fields_created": 0,
    }

    for table_name, table_cfg in sorted(schema.items()):
        if only_tables is not None and table_name.lower() not in only_tables:
            continue
        if not isinstance(table_cfg, dict):
            continue
        stats["tables_in_git"] += 1

        remote_container = containers_by_name.get(table_name.lower())
        if remote_container is None:
            stats["containers_missing"] += 1
            if args.verbose_missing:
                print(f"[import_specify_schema] missing container: {table_name}", file=sys.stderr)
            if args.create_missing and args.apply:
                remote_container = post_json(
                    session,
                    base,
                    "/api/specify/splocalecontainer/",
                    {
                        "name": table_name.lower(),
                        "discipline": f"/api/specify/discipline/{discipline_id}/",
                        "schematype": 0,
                        "ishidden": _norm_bool(table_cfg.get("ishidden")),
                        "issystem": False,
                        "version": 0,
                    },
                )
                containers_by_name[table_name.lower()] = remote_container
                stats["containers_created"] += 1
            elif args.create_missing and not args.apply:
                stats["containers_created"] += 1
            else:
                continue
        else:
            patch = _container_patch_body(remote_container, table_cfg)
            if patch is not None:
                stats["containers_changed"] += 1
                if args.apply:
                    cid = int(remote_container["id"])
                    put_json(session, base, f"/api/specify/splocalecontainer/{cid}/", patch)

        cid = int(remote_container["id"]) if remote_container else None
        if cid is None:
            continue

        remote_items = iter_list_endpoint(
            session,
            base,
            f"/api/specify/splocalecontaineritem/?container={cid}",
        )
        items_by_name = _index_items_by_name(remote_items)
        items_cfg = table_cfg.get("items") or {}
        if not isinstance(items_cfg, dict):
            continue

        for field_name, field_cfg in sorted(items_cfg.items()):
            if not isinstance(field_cfg, dict):
                continue
            stats["fields_in_git"] += 1
            remote_item = items_by_name.get(field_name.lower())
            desired_item = {
                "ishidden": field_cfg.get("ishidden"),
                "isrequired": field_cfg.get("isrequired"),
                "picklistname": field_cfg.get("picklistname"),
                "format": field_cfg.get("format"),
                "weblinkname": field_cfg.get("weblinkname"),
            }

            if remote_item is None:
                stats["fields_missing"] += 1
                if args.verbose_missing:
                    print(
                        f"[import_specify_schema] missing item: {table_name}.{field_name}",
                        file=sys.stderr,
                    )
                if args.create_missing and args.apply:
                    remote_item = post_json(
                        session,
                        base,
                        "/api/specify/splocalecontaineritem/",
                        {
                            "name": field_name,
                            "container": f"/api/specify/splocalecontainer/{cid}/",
                            "ishidden": _norm_bool(desired_item.get("ishidden")),
                            "isrequired": _norm_bool(desired_item.get("isrequired")),
                            "issystem": False,
                            "version": 0,
                            "picklistname": desired_item.get("picklistname"),
                            "format": desired_item.get("format"),
                            "weblinkname": desired_item.get("weblinkname"),
                            "type": field_cfg.get("type"),
                        },
                    )
                    items_by_name[field_name.lower()] = remote_item
                    stats["fields_created"] += 1
                elif args.create_missing:
                    stats["fields_created"] += 1
                continue

            patch = _item_patch_body(remote_item, desired_item)
            if patch is not None:
                stats["items_changed"] += 1
                if args.apply:
                    iid = int(remote_item["id"])
                    put_json(session, base, f"/api/specify/splocalecontaineritem/{iid}/", patch)

            iid = int(remote_item["id"])
            label_name = field_cfg.get("name")
            label_desc = field_cfg.get("desc")
            if _sync_locale_string(
                session,
                base,
                item_id=iid,
                name_key="itemname",
                language=language,
                country=country,
                text=str(label_name) if label_name is not None else None,
                dry_run=not args.apply,
            ):
                stats["labels_changed"] += 1
            if _sync_locale_string(
                session,
                base,
                item_id=iid,
                name_key="itemdesc",
                language=language,
                country=country,
                text=str(label_desc) if label_desc is not None else None,
                dry_run=not args.apply,
            ):
                stats["labels_changed"] += 1

    stats["applied"] = bool(args.apply)
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
