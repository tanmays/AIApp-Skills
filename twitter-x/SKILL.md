---
name: twitter-x
version: 1.0.0
description: This skill should be used when the user asks to "read my Twitter", "check X", "fetch my bookmarks", "get my twitter timeline", "search tweets", "look up an X user", "post a tweet", "reply on X", "like a tweet", "retweet", or otherwise read or write Twitter/X data programmatically. Drives a stdlib-only Python CLI against X's internal GraphQL API, authenticating with the cookies of a connected x.com account.
---

# twitter-x

Read and write Twitter/X data through X's internal GraphQL API. The skill is a
small, dependency-free Python CLI (`scripts/cli.py`) covering timelines,
bookmarks, search, user profiles, tweet threads, lists, followers/following, and
write actions (post, reply, like, retweet, bookmark).

Authentication uses the cookies of an **x.com account the user has already
connected** in the app — no API keys, no manual token copying.

## Authentication: use a connected x.com account

Credentials come from a connected account's cookie file, written by the app at:

```
config/websites/x.com/<account>/cookies.json
```

`cookies.json` is a JSON array of cookie objects; the CLI extracts `auth_token`
(session) and `ct0` (CSRF token) from it automatically.

Before running any command:

1. **Confirm an x.com connection exists.** List `config/websites/x.com/`. Each
   subdirectory is a connected account. If none exist, tell the user to connect
   one in **Settings → Connected Accounts → Add Account** (domain `x.com`), then
   stop — the skill cannot run without it.
2. **Let the CLI find the cookies.** When run from inside the workspace, the CLI
   walks up to locate `config/websites/x.com/<account>/cookies.json` on its own,
   so no flag is needed for the common single-account case.
3. **Disambiguate only when needed.** If several x.com accounts are connected,
   the CLI asks for one — pass `--cookies-file config/websites/x.com/<account>/cookies.json`.

If cookies are expired or invalid, API calls fail with an auth error. Ask the
user to **Re-authenticate** the connection in Settings, which rewrites
`cookies.json`.

## Running

The CLI uses only the Python standard library — there is nothing to install. Run
it as a module from the skill directory. Anchor the path to `$WORKSPACE` (the
absolute workspace root the terminal exports) so the command works regardless of
the current directory:

```bash
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli <command> [options]
```

Add `--json` to any read command for structured output instead of the formatted
text view.

## Commands

| Command | Purpose | Key arguments |
|---|---|---|
| `feed` | Home timeline | `--type for-you\|following`, `--max`, `--json` |
| `bookmarks` | Saved bookmarks | `--max`, `--json` |
| `bookmark-folders` | List bookmark folders | `--json` |
| `search` | Search tweets | `query`, `--tab Top\|Latest\|Photos\|Videos`, `--max`, `--json` |
| `user` | User profile (includes numeric `id`) | `screen_name`, `--json` |
| `user-posts` | Tweets posted by a user | `screen_name`, `--max`, `--json` |
| `user-likes` | Tweets a user liked (own account only) | `screen_name`, `--max`, `--json` |
| `tweet` | Tweet detail with reply thread | `tweet_id` (ID or URL), `--max`, `--json` |
| `tweet-by-id` | Single tweet, no replies (fast) | `tweet_id` (ID or URL), `--json` |
| `list` | Twitter List timeline | `list_id`, `--max`, `--json` |
| `followers` | Followers of a user | `user_id`, `--max`, `--json` |
| `following` | Accounts a user follows | `user_id`, `--max`, `--json` |
| `post` | Post a tweet or reply | `text`, `--reply-to <tweet_id>` |
| `delete` | Delete a tweet | `tweet_id` |
| `like` / `unlike` | Like or unlike | `tweet_id` |
| `retweet` / `unretweet` | Retweet or undo | `tweet_id` |
| `bookmark` / `unbookmark` | Add/remove bookmark | `tweet_id` |

`followers` and `following` need a numeric `user_id`, not a handle — resolve it
first with `user <screen_name>` and read the `id` field.

### Examples

All commands run from the skill directory, so prefix each with the `cd` above:

```bash
# First 20 bookmarks as JSON
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli bookmarks --max 20 --json

# Following timeline, formatted
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli feed --type following --max 30

# A user's profile and recent posts
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli user elonmusk
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli user-posts elonmusk --max 20

# A tweet and its thread (accepts a full URL)
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli tweet https://x.com/jack/status/20

# Post a reply
cd "$WORKSPACE/skills/twitter-x" && python3 -m scripts.cli post "Congrats!" --reply-to 1234567890
```

## Using it as a library

```python
from scripts.client import TwitterClient

client = TwitterClient(auth_token="…", ct0="…")
for tweet in client.fetch_bookmarks(count=20):
    print(f"@{tweet.author.screen_name}: {tweet.text[:80]}")
```

## How it works

- **Auth:** the two account cookies plus the public web Bearer token, with the
  `ct0` value mirrored into the `x-csrf-token` header.
- **queryId resolution:** X rotates the per-operation `queryId` in its web
  bundles. The client resolves each through a cache → bundled fallback →
  community list → live JS-bundle scan chain, and re-resolves automatically when
  a request returns 404.
- **Pagination & rate limits:** responses are paged via cursors up to `--max`,
  with jittered delays between requests and exponential backoff on HTTP 429/503.
  Reads use short delays; writes use longer ones.

## Notes and limitations

- **Search may be unavailable.** Since early 2026, X's `SearchTimeline` requires
  an `x-client-transaction-id` header this stdlib-only client cannot generate, so
  `search` can return 404. When it does, fall back to driving the in-app browser
  (the `web-search`/`webBrowser` path) against `x.com/search`.
- **Write actions carry account risk.** Posting, liking, retweeting, and deleting
  draw more scrutiny than reads — use them deliberately and sparingly.
- **`--max` is capped at 500** to avoid runaway requests.
- **Cookies expire** after weeks to months; on auth failures, have the user
  re-authenticate the x.com connection in Settings.
