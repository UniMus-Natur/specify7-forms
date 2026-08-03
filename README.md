# specify7-forms

Git-tracked Specify 7 **configuration as code** for Unimus: form/view XML,
discipline schema configuration (field visibility, labels, required flags),
WebLinks, and UI field formatters.

Specify ships UI export for schema and **no** official import/GitOps tooling; this
repo provides `export` / `plan` / `import` for forms and schema via the public API,
plus merge/upsert for WebLinks and UIFormatters.

## Quick start

```bash
./install.sh              # creates/repairs .venv, upgrades pip, pip install -e .
source .venv/bin/activate
specli --version
cp example.env .env
# edit .env
```

If a previous `pip install -e .` failed, remove the broken venv first: `rm -rf .venv && ./install.sh`

No install (works immediately):

```bash
./bin/specli form export --help
```

```bash
# Forms (viewsets)
specli form export --clean --no-manifests --output-dir forms
specli form plan --forms-dir forms
specli form import --forms-dir forms --apply

# Schema (per-discipline field config — one JSON file, not hundreds)
specli schema export --clean --output-dir schema
specli schema plan --schema-dir schema
specli schema import --schema-dir schema --apply

# UI field formatters (UIFormatters app resource — run before schema that references them)
specli formatter plan
specli formatter import --apply

# WebLinks
specli weblink plan
specli weblink import --apply
```

## Documentation

- [Forms git sync](docs/specify_forms_git_sync.md)
- [Schema git sync](docs/specify_schema_git_sync.md) — why exports are large, what exists upstream
- [UI field formatters git sync](docs/specify_formatters_git_sync.md)

## Repository layout

| Path | Purpose |
|------|---------|
| `specli` (package) / `bin/specli` | CLI entry point |
| `scripts/form.py` | Thin wrapper → `specli form` |
| `scripts/schema.py` | Thin wrapper → `specli schema` |
| `scripts/export_specify_forms.py` | Export view XML from Specify |
| `scripts/import_specify_forms.py` | Import view XML into DB viewsets |
| `scripts/export_specify_schema.py` | Export schema localization JSON |
| `scripts/import_specify_schema.py` | Import schema into `SpLocaleContainer*` |
| `scripts/import_specify_formatters.py` | Upsert UIFormatters XML |
| `scripts/import_specify_weblinks.py` | Merge WebLinks XML |
| `forms/` / `forms_all/` | Form XML trees |
| `schema/` | Schema JSON per discipline (created by export) |
| `resources/formatters/` | UIFormatter extension fragments |
| `resources/weblinks/` | WebLink extension fragments |
| `example.env` | Template for `.env` credentials |
