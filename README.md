# vibefetch

CLI utility to compute LLM token and cost statistics for local Claude, Codex, and Gemini CLI logs. It uses LiteLLM pricing data and can render hourly or daily stacked bar charts in the terminal.

## Requirements

- Python 3.10+
- `plotext` for charts (already listed in `requirements.txt`)

Install dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

Run with defaults (last 7 days):

```bash
python -m vibefetch.cost_stats
```

Daily table:

```bash
python -m vibefetch.cost_stats --daily
```

Hourly chart:

```bash
python -m vibefetch.cost_stats --hourly-chart
```

Daily chart:

```bash
python -m vibefetch.cost_stats --daily-chart
```

Both charts:

```bash
python -m vibefetch.cost_stats --hourly-chart --daily-chart
```

## Log Sources

By default the tool reads:

- Claude: `~/.claude/history.jsonl` and `~/.claude/projects/**/*.jsonl`
- Codex: `~/.codex/history.jsonl` and `~/.codex/sessions/**/*.jsonl`
- Gemini: `~/.gemini/tmp/**/chats/session-*.json`

Override roots if needed:

```bash
python -m vibefetch.cost_stats --claude-root /path/to/claude --codex-root /path/to/codex --gemini-root /path/to/gemini
```

## Pricing Data

Pricing is fetched from LiteLLM’s GitHub JSON and cached locally. If the fetch times out, cached data is used.

Override pricing URL or timeout:

```bash
python -m vibefetch.cost_stats --pricing-url URL --timeout 5
```

## Filtering and Models

Set a custom date range:

```bash
python -m vibefetch.cost_stats --from 2026-03-01 --to 2026-03-07
```

Limit chart models:

```bash
python -m vibefetch.cost_stats --hourly-chart --chart-top 4
python -m vibefetch.cost_stats --hourly-chart --chart-models gpt-5.4,claude-opus-4-6
```

## Output Columns

The table reports, per model:

- `input_tokens`
- `output_tokens`
- `cache_refill_tokens`
- `cache_hit_tokens`
- `kv_cache_hit_rate`
- `total_tokens`
- `cost_usd`

A TOTAL row is shown at the bottom for the selected time span.

## Notes

- `input_tokens` is total input (cached + uncached).
- `cache_refill_tokens` is uncached input (KV cache refill).
- `cache_hit_tokens` is cached input.
- `kv_cache_hit_rate` is `cache_hit_tokens / input_tokens`.
- For Codex/Gemini logs, `cache_refill_tokens` is derived as `input_tokens - cache_hit_tokens`.
- Cache token fields are shown as `N/A` if not present in logs.
- Models missing from the LiteLLM pricing table are reported with $0 cost.
