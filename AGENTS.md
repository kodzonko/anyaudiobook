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

## Testing

- Try to keep test coverage above 90% if feasible. Do not add tests just for the sake of increasing coverage. Add tests for new features and bug fixes, and for any code that is complex or has a high risk of failure. If you are unsure whether a test is needed, ask me.
- If a bug is reported or found out by you, write a test that reproduces the bug and then fix the bug. This ensures that the bug does not reappear in the future.
- Prioritise e2e then integration tests. It's best to test functionalities with real-world scenarios and setup rather than overrelying on mocks and patches. E2e tests should cover the most important user flows and scenarios, integration tests should cover the interactions between different components. Unit tests should cover scenarios hard to reproduce in e2e or integration tests without mocking. If you are unsure about what type of test to write, ask me.
