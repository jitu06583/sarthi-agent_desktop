---
sidebar_position: 4
title: "Buzz Integration"
description: "All three ways to connect Sarthi Agent to Buzz — Block's Nostr-based human+agent workspace"
---

# Buzz Integration

[Buzz](https://github.com/block/buzz) is Block's open-source, self-hostable workspace where humans and AI agents share the same channels. It is built on Nostr: every message is a signed event on a relay you own, and every participant — human or agent — is a keypair.

Sarthi integrates with Buzz three ways. Pick by where Sarthi runs and what you want it to do:

| | ① Desktop runtime | ② Relay bridge (ACP) | ③ Native gateway platform |
|---|---|---|---|
| **What it is** | Buzz Desktop spawns Sarthi locally as a managed harness | Buzz's `buzz-acp` bridges a channel to `sarthi acp` over stdio | Sarthi' gateway joins Buzz as a first-class messaging platform |
| **Sarthi runs** | On your desktop, launched by Buzz | On a server, launched by `buzz-acp` | In your own gateway, alongside Telegram/Discord/etc. |
| **Best for** | Trying Sarthi inside Buzz Desktop with zero config | A hosted agent identity when Buzz owns the transport | Full Sarthi: memory, skills, approvals, cron, sessions |
| **Inbound** | ACP stdio | ACP stdio (via relay WebSocket) | NIP-42-authenticated Nostr WebSocket (poll fallback) |
| **Setup** | Automatic discovery | `buzz-acp` env vars | `sarthi gateway setup` → Buzz |

## ① Buzz Desktop managed runtime

Buzz Desktop ships Sarthi as a preset runtime. With Sarthi installed the normal way, open **Settings → Runtimes** and Sarthi appears automatically — discovery resolves the `sarthi-acp` launcher on your login-shell PATH, which the installer writes to `~/.local/bin` (and `sarthi update` self-heals on older installs).

Full setup, troubleshooting, and the security posture (Buzz auto-approves tool permissions — keep agents owner-only): **[ACP Host Integration → Buzz Desktop](/user-guide/features/acp#buzz-desktop)**

## ② Relay bridge (buzz-acp + ACP)

For a hosted Sarthi identity that joins Buzz *channels* while Buzz's own harness owns the transport:

```text
Buzz relay <-- WebSocket --> buzz-acp <-- ACP over stdio --> Sarthi Agent
```

The spawned Sarthi uses the same config, credentials, memory, and skills as `sarthi` on that host. Key minting, channel discovery, owner-only telemetry (`BUZZ_ACP_RELAY_OBSERVER`), and headless-permission guidance: **[ACP Host Integration → Buzz channels (relay bridge)](/user-guide/features/acp#buzz-channels-relay-bridge)**

## ③ Native gateway platform (recommended for full Sarthi)

The bundled `buzz` platform plugin makes Buzz a normal Sarthi messaging platform — channels, DMs, mention gating, threaded replies, reactions, images, and cron delivery (`deliver=buzz`), with Sarthi' own approvals, memory, and session management intact. Inbound arrives over a persistent NIP-42-authenticated Nostr WebSocket (dependency-free BIP-340 signing) with automatic fallback to CLI polling; outbound goes through the `buzz` CLI.

```bash
sarthi gateway setup   # pick Buzz
```

Full configuration reference (env vars, config.yaml, transport modes, access control): **[Messaging → Buzz](/user-guide/messaging/buzz)**

## Which one should I use?

- **Just exploring, Buzz Desktop user** → ① works out of the box.
- **Running a community relay and want an agent identity managed by Buzz** → ②.
- **You already run Sarthi as your agent and want Buzz as another channel** → ③. This is the deepest integration and the one that keeps every Sarthi feature.

①/② and ③ use different identities and transports; run ③ with its own dedicated Nostr keypair. The adapter takes a scoped lock on the relay+pubkey pair, so two Sarthi profiles cannot accidentally drive one Buzz identity.

## Credits

The Buzz integration was built with the community: @SHL0MS (PATH launcher + Desktop security audit), @NYTEMODEONLY (relay-bridge docs), @rob-coco (platform adapter), @ScaleLeanChris (Nostr WebSocket transport + NIP-42/BIP-340 signing), and @jethac (multi-agent verification).
