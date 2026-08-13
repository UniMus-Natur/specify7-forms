# specify7-forms

Git-tracked Specify 7 **configuration as code** for Unimus: form/view XML,
discipline schema configuration (field visibility, labels, required flags),
WebLinks, and UI field formatters.

`specli` talks to Specify with git-style verbs:

| Command | Direction | Was |
|---------|-----------|-----|
| `pull` | Specify → git | `export` |
| `push` | git → Specify | `import --apply` |
| `status` | dry-run push | `plan` |

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
./bin/specli form pull --help
```

```bash
# Forms (viewsets)
specli form pull --clean --no-manifests --output-dir forms
specli form status --forms-dir forms
specli form push --forms-dir forms

# Schema (per-discipline field config — one JSON file, not hundreds)
specli schema pull --clean --output-dir schema
specli schema status --schema-dir schema
specli schema push --schema-dir schema

# UI field formatters (UIFormatters app resource — run before schema that references them)
specli formatter status
specli formatter push

# Table/query display (Taxon fullName + author on determinations, query boxes)
specli dataobjformatter status
specli dataobjformatter push

# WebLinks
specli weblink status
specli weblink push
```

`push --dry-run` is the same as `status`. Legacy `export` / `import` / `plan` aliases still work.

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
| `scripts/export_specify_forms.py` | Pull view XML from Specify |
| `scripts/import_specify_forms.py` | Push view XML into DB viewsets |
| `scripts/export_specify_schema.py` | Pull schema localization JSON |
| `scripts/import_specify_schema.py` | Push schema into `SpLocaleContainer*` |
| `scripts/import_specify_formatters.py` | Push UIFormatters XML |
| `scripts/import_specify_dataobj_formatters.py` | Push DataObjFormatters XML (Taxon display) |
| `scripts/import_specify_weblinks.py` | Push WebLinks XML |
| `forms/` / `forms_all/` | Form XML trees |
| `schema/` | Schema JSON per discipline (created by pull) |
| `resources/formatters/` | UIFormatter extension fragments |
| `resources/dataobj_formatters/` | DataObjFormatter extension fragments (Taxon, Determination, …) |
| `resources/weblinks/` | WebLink extension fragments |
| `example.env` | Template for `.env` credentials |
