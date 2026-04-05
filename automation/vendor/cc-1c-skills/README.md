# Vendored `cc-1c-skills` Import

Этот каталог содержит vendored upstream pack из `cc-1c-skills`, используемый для генерации `.agents/skills` и `.claude/skills` compatibility surface.

## Provenance

- source: `git@github.com:Nikolay-Shirokov/cc-1c-skills.git`
- commit: `eebc2a06792c6c0263ce02bb6c63b8a4579134d1`
- synced at: `2026-04-05T09:56:56Z`
- license: [`LICENSE`](LICENSE)

## Layout

- `skills/<name>/` — upstream skill directories from `.claude/skills/`
- `imported-skills.json` — checked-in manifest for dispatch/generation

## Refresh

```bash
python -m scripts.python.cli sync-imported-skills --source /path/to/cc-1c-skills
./scripts/llm/export-context.sh --write
```

## Imported Skills

- count: `67`
- dispatcher: `./scripts/skills/run-imported-skill.sh <skill>` / `./scripts/skills/run-imported-skill.ps1 <skill>`

Do not edit vendored generated skill facades manually; regenerate them from this vendor source instead.
