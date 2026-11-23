# Contributing to Panko

Thanks for helping. Bug reports, new language setups, fixes and ideas are all welcome.

## Before you open a pull request
- Read [docs/DECISIONS.md](docs/DECISIONS.md) and the hard rules in [CLAUDE.md](CLAUDE.md). The most important rule:
  never change the field lists or card templates in a way that forces Anki into a full sync, because learners would
  lose their sync state.
- Run the tests and the linter:

  ```bash
  uv run pytest -q
  ```

  ```bash
  uv run ruff check .
  ```

- Keep personal choices out of the code and the prompts. They belong in the learner's `config/panko.toml`.

## Contributor agreement
Panko is licensed under the AGPL-3.0-or-later. So that the project can change its licence later, for example to
offer a commercial licence next to the AGPL or to run a hosted service, every contribution is made under this
agreement:

1. You keep the copyright in your contribution.
2. You grant the Panko maintainer (NotAHill) and their successors a perpetual, worldwide, non-exclusive,
   royalty-free, irrevocable licence to use, copy, modify, distribute and sublicense your contribution, and to
   release it under other licence terms, including proprietary ones.
3. You confirm the contribution is your own work, or that you have the right to submit it under these terms, and
   that it doesn't include code or data whose licence conflicts with them.
4. Your contribution is also available to everyone under the AGPL-3.0-or-later, like the rest of Panko.

To agree, add this line to your pull request description:

> I have read CONTRIBUTING.md and I agree to the contributor agreement for this and my future contributions to Panko.
