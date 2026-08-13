#!/usr/bin/env python3
"""Merge git-tracked table formatters into Specify App Resource ``DataObjFormatters``.

Reads ``resources/dataobj_formatters/*.xml`` (``<formatters>`` fragments with ``<format name>``
children), fetches the discipline-scoped ``DataObjFormatters`` resource via the public
API, and upserts ``<format>`` definitions by ``@name`` (add missing, replace existing).
``<aggregators>`` and other siblings are left unchanged.

When Specify serves DataObjFormatters from the filesystem backstop only
(``X-Record-ID`` empty / ``None``), creates a discipline DB app resource with the
merged XML so custom formatters persist.

Dry-run by default. Use ``--apply`` to write.

Usage:
  specli dataobjformatter status
  specli dataobjformatter push
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

from _specify_client import (
    disable_insecure_request_warnings,
    iter_list_endpoint,
    load_env_from_repo,
    login,
    post_json,
    put_json,
    require_env,
    resolve_specify_user_id,
    resource_pk,
    strip_meta_for_put,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FORMATTERS_DIR = REPO_ROOT / "resources" / "dataobj_formatters"
LOG = "import_specify_dataobj_formatters"
RESOURCE_NAME = "DataObjFormatters"


def _load_formats_from_path(path: Path) -> list[ET.Element]:
    root = ET.fromstring(path.read_text(encoding="utf-8"))
    if root.tag == "format":
        return [root]
    if root.tag != "formatters":
        sys.exit(f"{path}: expected <formatters> root, got <{root.tag}>")
    return list(root.findall("format"))


def _load_extension_formats() -> list[tuple[str, ET.Element]]:
    if not FORMATTERS_DIR.exists():
        sys.exit(f"DataObjFormatters directory not found: {FORMATTERS_DIR}")
    out: list[tuple[str, ET.Element]] = []
    for path in sorted(FORMATTERS_DIR.glob("*.xml")):
        if path.name == "defaults.xml":
            continue
        for element in _load_formats_from_path(path):
            name = (element.attrib.get("name") or "").strip()
            if not name:
                sys.exit(f"{path}: <format> missing name attribute")
            out.append((name, element))
    return out


def _parse_record_id(header_value: str | None) -> int | None:
    if header_value is None:
        return None
    text = str(header_value).strip()
    if not text or text.lower() in ("none", "null"):
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _existing_format_index(root: ET.Element) -> dict[str, ET.Element]:
    if root.tag != "formatters":
        sys.exit(f"Expected <formatters> root in {RESOURCE_NAME} XML, got <{root.tag}>")
    index: dict[str, ET.Element] = {}
    for element in root.findall("format"):
        name = (element.attrib.get("name") or "").strip()
        if name:
            index[name] = element
    return index


def _xml_declaration(body: str) -> str:
    if body.startswith("<?xml"):
        return body
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + body


def _merge_formatters(
    existing_xml: str,
    extensions: list[tuple[str, ET.Element]],
) -> tuple[str, list[str], list[str]]:
    """Upsert <format> by @name. Returns (xml, added_names, updated_names)."""
    root = ET.fromstring(existing_xml)
    present = _existing_format_index(root)
    added: list[str] = []
    updated: list[str] = []
    changed = False

    for name, element in extensions:
        if name in present:
            old = present[name]
            old_s = ET.tostring(old, encoding="unicode")
            new_s = ET.tostring(element, encoding="unicode")
            if old_s == new_s:
                continue
            root.remove(old)
            root.append(element)
            present[name] = element
            updated.append(name)
            changed = True
        else:
            root.append(element)
            present[name] = element
            added.append(name)
            changed = True

    if not changed:
        return existing_xml, added, updated
    return _xml_declaration(ET.tostring(root, encoding="unicode")), added, updated


def _find_discipline_resource_dir(session, base: str, collection_id: int) -> int:
    rows = iter_list_endpoint(
        session,
        base,
        f"/api/specify/spappresourcedir/?collection={collection_id}&limit=100",
    )
    for row in rows:
        if not row.get("ispersonal") and not row.get("usertype"):
            dir_id = resource_pk(row.get("resource_uri"))
            if dir_id is not None:
                return dir_id
    for row in rows:
        if not row.get("ispersonal"):
            dir_id = resource_pk(row.get("resource_uri"))
            if dir_id is not None:
                return dir_id
    sys.exit("No discipline SpAppResourceDir found for this collection")


def _create_resource(
    session,
    base: str,
    *,
    collection_id: int,
    specify_user_id: int,
    merged_xml: str,
) -> tuple[int, int]:
    dir_id = _find_discipline_resource_dir(session, base, collection_id)
    resource = post_json(
        session,
        base,
        "/api/specify/spappresource/",
        {
            "name": RESOURCE_NAME,
            "mimetype": "text/xml",
            "metadata": RESOURCE_NAME,
            "description": RESOURCE_NAME,
            "level": 0,
            "spappresourcedir": f"/api/specify/spappresourcedir/{dir_id}/",
            "specifyuser": f"/api/specify/specifyuser/{int(specify_user_id)}/",
        },
    )
    resource_id = resource_pk(resource.get("resource_uri"))
    if resource_id is None:
        sys.exit("Could not parse created spappresource id")

    data_row = post_json(
        session,
        base,
        "/api/specify/spappresourcedata/",
        {
            "data": merged_xml,
            "spappresource": f"/api/specify/spappresource/{resource_id}/",
        },
    )
    data_id = resource_pk(data_row.get("resource_uri"))
    if data_id is None:
        sys.exit("Could not parse created spappresourcedata id")
    return resource_id, data_id


def _put_spappresourcedata(session, base: str, resource_id: int, merged_xml: str) -> int:
    data_rows = iter_list_endpoint(
        session,
        base,
        f"/api/specify/spappresourcedata/?spappresource={int(resource_id)}&limit=1",
    )
    if not data_rows:
        sys.exit(f"No spappresourcedata row for spappresource id={resource_id}")
    data_row = data_rows[0]
    data_id = resource_pk(data_row.get("resource_uri"))
    if data_id is None:
        sys.exit("Could not parse spappresourcedata id")
    body = strip_meta_for_put(data_row)
    body["data"] = merged_xml
    put_json(session, base, f"/api/specify/spappresourcedata/{data_id}/", body)
    return data_id


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"Import table formatters ({RESOURCE_NAME}) into Specify"
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("SPECIFY7_COLLECTION") or None,
        help="Specify collection to log into (default: SPECIFY7_COLLECTION env, else first available)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help=f"Write merged {RESOURCE_NAME} to Specify",
    )
    args = parser.parse_args()

    load_env_from_repo()
    disable_insecure_request_warnings()

    base = require_env("SPECIFY7_URL").rstrip("/")
    user = require_env("SPECIFY7_USER")
    password = require_env("SPECIFY7_PASSWORD")
    collection_name = (args.collection or "").strip() or None

    extensions = _load_extension_formats()
    if not extensions:
        print(f"[{LOG}] no extension formatters found", file=sys.stderr)
        return

    session, selected_collection, col_id = login(
        base,
        user,
        password,
        collection_name,
        log_prefix=LOG,
    )
    specify_user_id = resolve_specify_user_id(session, base, user)

    res = session.get(f"{base}/context/app_resource?name={RESOURCE_NAME}", timeout=60)

    if res.status_code == 404:
        root = ET.Element("formatters")
        for _, element in extensions:
            root.append(element)
        merged_xml = _xml_declaration(ET.tostring(root, encoding="unicode"))
        added = [name for name, _ in extensions]
        print(
            f"[{LOG}] {RESOURCE_NAME} missing — would create with: {', '.join(added)} "
            f"(collection={selected_collection})",
            file=sys.stderr,
        )
        if not args.apply:
            print(f"[{LOG}] dry-run — pass --apply to write", file=sys.stderr)
            return
        resource_id, data_id = _create_resource(
            session,
            base,
            collection_id=col_id,
            specify_user_id=specify_user_id,
            merged_xml=merged_xml,
        )
        print(
            f"[{LOG}] created {RESOURCE_NAME} spappresource={resource_id} "
            f"spappresourcedata={data_id}; definitions: {', '.join(added)}",
            file=sys.stderr,
        )
        return

    if res.status_code != 200:
        sys.exit(f"GET {RESOURCE_NAME} failed ({res.status_code}): {res.text[:500]}")

    resource_id = _parse_record_id(res.headers.get("X-Record-ID"))
    merged_xml, added, updated = _merge_formatters(res.text, extensions)

    if not added and not updated:
        print(
            f"[{LOG}] nothing to do — all {len(extensions)} formatter(s) already present "
            f"(collection={selected_collection})",
            file=sys.stderr,
        )
        return

    parts = []
    if added:
        parts.append(f"add: {', '.join(added)}")
    if updated:
        parts.append(f"update: {', '.join(updated)}")
    action = "; ".join(parts)

    if resource_id is None:
        print(
            f"[{LOG}] {RESOURCE_NAME} served from filesystem backstop (no DB row) — "
            f"would create discipline resource and {action} "
            f"(collection={selected_collection})",
            file=sys.stderr,
        )
        if not args.apply:
            print(f"[{LOG}] dry-run — pass --apply to write", file=sys.stderr)
            return
        new_id, data_id = _create_resource(
            session,
            base,
            collection_id=col_id,
            specify_user_id=specify_user_id,
            merged_xml=merged_xml,
        )
        print(
            f"[{LOG}] created {RESOURCE_NAME} spappresource={new_id} "
            f"spappresourcedata={data_id}; {action}",
            file=sys.stderr,
        )
        return

    print(
        f"[{LOG}] would {action} (collection={selected_collection}, "
        f"spappresource={resource_id})",
        file=sys.stderr,
    )
    if not args.apply:
        print(f"[{LOG}] dry-run — pass --apply to write", file=sys.stderr)
        return

    data_id = _put_spappresourcedata(session, base, resource_id, merged_xml)
    print(
        f"[{LOG}] updated {RESOURCE_NAME} (spappresourcedata id={data_id}); {action}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
