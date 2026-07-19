# Langfuse Observability Plugin

This plugin ships bundled with Sarthi but is **opt-in** — it only loads when
you explicitly enable it.

## Enable

Pick one:

```bash
# Interactive: walks you through credentials + SDK install + enable
sarthi tools  # → Langfuse Observability

# Manual
pip install langfuse
sarthi plugins enable observability/langfuse
```

## Required credentials

Set these in `~/.sarthi/.env` (or via `sarthi tools`):

```bash
SARTHI_LANGFUSE_PUBLIC_KEY=pk-lf-...
SARTHI_LANGFUSE_SECRET_KEY=sk-lf-...
SARTHI_LANGFUSE_BASE_URL=https://cloud.langfuse.com   # or your self-hosted URL
```

Without the SDK or credentials the hooks no-op silently — the plugin fails
open.

## Verify

```bash
sarthi plugins list                 # observability/langfuse should show "enabled"
sarthi chat -q "hello"              # then check Langfuse for a "Sarthi turn" trace
```

## Optional tuning

```bash
SARTHI_LANGFUSE_ENV=production       # environment tag
SARTHI_LANGFUSE_RELEASE=v1.0.0       # release tag
SARTHI_LANGFUSE_SAMPLE_RATE=0.5      # sample 50% of traces
SARTHI_LANGFUSE_MAX_CHARS=12000      # max chars per field (default: 12000)
SARTHI_LANGFUSE_DEBUG=true           # verbose plugin logging
```

## Disable

```bash
sarthi plugins disable observability/langfuse
```
