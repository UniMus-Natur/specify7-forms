# Specify UI field formatters git sync

Field formatters (input masks / regex validation) live in the Specify app
resource **`UIFormatters`** — XML under a `<formats>` root. Schema config only
stores the **name** of a formatter on each field (`format` in `schema.en.json`);
the definition itself must exist in `UIFormatters`.

`specli formatter` merges git-tracked fragments into that app resource (same idea
as `specli weblink`).

Entry point: **`specli formatter`** (wraps `import_specify_formatters.py`).

## Setup

Same as forms/schema — from repo root:

```bash
./install.sh
source .venv/bin/activate
cp example.env .env
```

## Commands

```bash
# Dry-run: what would be added/updated?
specli formatter plan

# Apply to the logged-in collection’s discipline
specli formatter import --apply
```

## On-disk layout

```
resources/formatters/
  karplaner.xml     # <formats> with one or more <format name="…">
```

Optional `defaults.xml` is reserved for a future full bootstrap copy; extension
files (everything except `defaults.xml`) are upserted by `@name`.

Example (Norwegian MGRS grid reference on `Locality.text3`):

```xml
<formats>
  <format
    system="false"
    name="GridRefMGRS"
    class="edu.ku.brc.specify.datamodel.Locality"
    fieldname="text3"
    default="false"
  >
    <field
      type="regex"
      value="[A-Za-z]{1,3}\s+\d{1,5}(?:-\d{1,5})?\s*,\s*\d{1,6}(?:-\d{1,6})?"
      pattern="AA 000,000"
    />
  </format>
</formats>
```

Then set `"format": "GridRefMGRS"` on the field in schema JSON and run
`specli schema import --apply`.

## Semantics

| Situation | Behaviour |
|-----------|-----------|
| Formatter `@name` missing on server | **Add** |
| Same `@name`, different XML | **Replace** |
| Same `@name`, identical XML | No-op |
| `UIFormatters` only on filesystem backstop (`X-Record-ID` empty) | **Create** discipline DB resource with backstop XML + extensions |

Unlike DataObjFormatters, Specify does **not** merge filesystem + DB for
`UIFormatters` — a DB row at discipline level shadows the backstop. The import
therefore starts from the currently served XML (backstop or DB) before upserting.

## Recommended order

1. `specli formatter import --apply` — definitions exist
2. `specli schema import --apply` — fields point at formatter names
3. `specli form import --apply` — labels / layout

## Limits (v1)

- No export round-trip (git owns extension fragments).
- Does not sync DataObjFormatters (table/query display aggregators).
- Upserts only names present under `resources/formatters/` (does not delete remote-only formatters).
