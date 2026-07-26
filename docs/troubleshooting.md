# When something breaks

Symptoms first. Each section starts with what you'd actually observe.

> Part of **buzz-ai** — see [README](../README.md) for the map.

## If an agent seems unresponsive

Read the channel straight off the relay, bypassing the desktop app — if the reply is here
but not in the app, the problem is the app (stale member cache), not the agent:

```bash
docker exec buzz-ai-agents-1 sh -c \
  'BUZZ_PRIVATE_KEY="$OPERATIONS_NSEC" BUZZ_AUTH_TAG="$OPERATIONS_AUTH_TAG" \
   buzz messages get --channel <channel-id> --limit 10'
```

Other quick checks: `docker compose logs -f`, and confirm the agent isn't simply idle
because it was never added to the channel.

## Re-login loops (when auth breaks)
- **Claude:** token lasts ~1 year → re-run `claude setup-token`, update the
  `claude_oauth_token` secret in Bitwarden.
- **Codex:** if it stops working → `codex login` on your Mac → update the five
  `codex_*` secrets in Bitwarden from the new `~/.codex/auth.json`.

Either way: `python3 start.py --down && python3 start.py` to pick up the new values.
