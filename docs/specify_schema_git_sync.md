# Specify schema configuration git sync

Schema configuration controls which datamodel fields are visible, required, labeled,
and how they behave (pick lists, formats). In Specify this lives in
`SpLocaleContainer` / `SpLocaleContainerItem` per **discipline** — not in form XML.

This repo syncs that config the same way as forms: **export** (instance → git),
**plan** (dry-run), **import --apply** (git → instance).

## Why so many entries?

There are not hundreds of separate “schemas”. There is **one schema config per
discipline**, containing rows for **every table and field** in the Specify datamodel
(~200 tables × many fields each). That is why a full export is large.

Git layout uses **one JSON file per discipline** (plus optional per-table splits),
not one file per field.

## Existing Specify tooling?

| Tool | Status |
|------|--------|
| Schema Config UI → Export | Downloads `/context/schema_localization.json` (same shape we use) |
| Schema Config UI → Import | **Not implemented** ([specify7#6155](https://github.com/specify/specify7/issues/6155)) |
| `config/<discipline>/schema_overrides.json` in Docker image | Bootstrap defaults only; not a full GitOps round-trip |
| `fix_schema_config` / `apply_schema_defaults` | Server startup/migration helpers — **do not use** for GitOps deploy |

So API-based export/import in this repo fills a real gap; you are not duplicating
official provisioning tooling.

## Setup

Same as forms — from repo root:

```bash
./install.sh
source .venv/bin/activate
cp example.env .env
```

## Commands

```bash
# Export full discipline schema (GitOps baseline)
specli schema export --output-dir schema --clean

# Dry-run: what would change on the server?
specli schema plan --schema-dir schema

# Apply git state to Specify
specli schema import --schema-dir schema --apply

# Only sync tables you care about (smaller PRs)
specli schema export --only-tables accession,collectionobject --output-dir schema
specli schema import --schema-dir schema --only-tables accession,collectionobject --apply
```

## On-disk layout

```
schema/
  summary.json
  <discipline-slug>/          # e.g. from discipline.type
    meta.json                 # discipline/collection ids, export metadata
    schema.en.json            # full schema (UI export format)
    tables/                   # optional, with --split-tables
      collectionobject.json
      accession.json
```

`schema.en.json` keys are lowercase table names; each table has `items` keyed by
field name with `ishidden`, `isrequired`, `name`, `desc`, `picklistname`, etc.

## GitOps workflow

1. **Bootstrap:** `schema.py export --clean` → commit `schema/<slug>/`.
2. **Edit in git:** change `ishidden`, labels, `isrequired` in JSON (or use UI then re-export).
3. **Promote:** `plan` on staging → `import --apply` → same on prod.
4. **Revert:** `git revert` + `import --apply`.

Keep **forms** (`forms/`) and **schema** (`schema/`) in sync when adding fields to
forms: enable the field in schema (`ishidden: false`) and add the cell in form XML.

## Limits (v1)

- Syncs discipline schema for the logged-in collection’s discipline.
- Label sync for one language per bundle (`schema.<lang>.json`).
- Does not manage pick list definitions or viewsets (use forms sync / ensure scripts).
- Field `format` names are synced; formatter **definitions** are managed by
  [`specli formatter`](specify_formatters_git_sync.md) (`UIFormatters` app resource).
- `--create-missing` can add container/item rows; prefer export after discipline bootstrap.
