# AGENTS.md

This document describes the design principles and project structure for `vibefetch`.

## Design Principles

- **Single responsibility per module**: each file focuses on one concern (logs, pricing, aggregation, rendering, CLI).
- **Explicit data models**: all shared data structures are defined in `models.py`.
- **Pure functions where possible**: transformations and computations avoid side effects.
- **Graceful failure**: missing logs, missing pricing, or partial fields do not crash the CLI.
- **Human-friendly output**: table totals, readable token counts, and clear chart legends.
- **Minimal dependencies**: only `plotext` is required for charts; core logic uses stdlib.

## Project Structure

```
vibefetch/
  README.md               Usage instructions for humans
  requirements.txt        Python dependencies
  vibefetch/
    __init__.py            Package marker
    __main__.py            Module entry point
    cost_stats.py          CLI entry, orchestration
    constants.py           Global constants (pricing URL, cache path, timezone)
    models.py              Dataclasses for records, pricing, aggregated stats
    utils.py               Shared helpers (JSONL parsing, dates, formatting)
    logs.py                Log discovery + parsers for Claude/Codex/Gemini
    pricing.py             LiteLLM pricing fetch + cache + normalization
    aggregate.py           Aggregation + token/cost calculations
    table.py               Table rendering (including totals)
    chart.py               Chart rendering (hourly/daily stacked bars)
```

## Data Flow

1. **Log parsing** (`logs.py`): read local CLI logs and emit `Record` objects.
2. **Filtering** (`logs.py` + `utils.py`): restrict records by date, drop synthetic models.
3. **Pricing** (`pricing.py`): fetch/cache LiteLLM pricing and build the price index.
4. **Aggregation** (`aggregate.py`): compute per-model stats and cost in USD.
5. **Rendering** (`table.py`, `chart.py`): output a table and optional charts.
6. **CLI orchestration** (`cost_stats.py`): wires everything together.

## Extension Guidelines

- New log sources should add a parser in `logs.py` and return `Record` objects.
- New output formats should be implemented in a new module and called from `cost_stats.py`.
- Keep dependencies minimal and prefer stdlib unless charts or formatting require otherwise.

## Commit Convention

- Use Angular/Conventional Commit format for all commits: `type(scope): summary`.
- Prefer concise lowercase `type` values such as `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
