## Code quality

- Run `uv run ruff check --fix`, `uv run ruff format` and `uv run ty check` after finishing code changes to ensure code quality and consistency. Fix any issues reported if feasbile. If not report leftover issues to me.

## Dependencies

- Always use strict version pinning for dependencies in `pyproject.toml`
- When adding new dependencies, defauly to latest stable versions unless there is a specific reason to use a different version. If you are unsure, ask me.

## Git

- when committing code, use conventional commit syntax (https://www.conventionalcommits.org/en/v1.0.0/). For example, `feat: add new feature`, `fix: fix a bug`, `docs: update documentation`.

## Docs

- Keep README.md short and focused on basic usage and features. For more detailed documentation, use markdown files in the `docs/` directory.
- When a meaningful change is made to the codebase, update the relevant documentation in `docs/` and/or `README.md` as needed.
