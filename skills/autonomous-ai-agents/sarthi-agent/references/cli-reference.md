# Sarthi CLI Reference

Live sources when anything looks stale: `sarthi --help`, `sarthi <command> --help`,
https://hermes-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
sarthi [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
sarthi chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
sarthi setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
sarthi model                Interactive model/provider picker
sarthi fallback [add|remove|list]  Fallback provider chain
sarthi config [show|edit|get|set|unset|path|env-path|check|migrate]
sarthi login / logout       OAuth sign-in / clear stored auth
sarthi doctor [--fix]       Check dependencies and config
sarthi status [--all]       Component status
```

### Tools & Skills

```
sarthi tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

sarthi skills list|browse|search QUERY|inspect ID
sarthi skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
sarthi skills config        Enable/disable skills per platform
sarthi skills check|update|uninstall|publish PATH
sarthi skills tap add REPO  Add a GitHub repo as a skill source
sarthi bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
sarthi mcp add NAME (--url or --command) | remove | list | test NAME
sarthi mcp catalog | install NAME     Curated catalog install
sarthi mcp configure NAME             Toggle tool selection
sarthi mcp serve                      Run Sarthi as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
sarthi gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `sarthi photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
sarthi sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
sarthi cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
sarthi webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
sarthi profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
sarthi profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
sarthi auth                 Interactive credential manager
sarthi auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
sarthi auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
sarthi desktop / gui        Native desktop app
sarthi dashboard            Web admin panel + embedded chat (--stop / --status)
sarthi proxy                OpenAI-compatible local proxy backed by an OAuth provider
sarthi portal               Quick setup / sign in via Nous Portal
sarthi kanban <verb>        Multi-agent work-queue board
sarthi project              Named multi-folder workspaces
sarthi skin list|use|set    Switch/tweak skins (see references/themes.md)
sarthi pets <verb>          Pet mascots (see references/petdex.md)
sarthi memory setup|status|off|reset   Memory provider
sarthi secrets bitwarden|onepassword   External secret stores
sarthi moa                  Mixture-of-Agents slots
sarthi hooks / security / backup / import / checkpoints / console
sarthi logs [-f] [errors]   View agent/error logs
sarthi send                 One-off message through a gateway platform
sarthi pairing / plugins / insights / journey / computer-use
sarthi acp                  ACP server (IDE integration)
sarthi completion bash|zsh|fish
sarthi update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `sarthi photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `sarthi config edit` · [Configuration docs](https://hermes-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `sarthi tools list` · [Tools reference](https://hermes-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `sarthi skills browse` · [Skills catalog](https://hermes-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `sarthi model` · [Providers guide](https://hermes-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `sarthi config env-path` · [Env vars reference](https://hermes-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.sarthi/logs/gateway.log` (or `sarthi logs`) |
| Sessions | `sarthi sessions browse` (reads state.db) |
