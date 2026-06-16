---
name: web-search
version: 1.0.0
description: This skill should be used when the user asks to "search the web", "look this up online", "search for", "find this on the internet", "google this", or needs real-time information from search engines instead of model memory. Drives WebBrowserTool across multiple English-language engines (Perplexity, Google, Bing, Brave, DuckDuckGo) with automatic fallback when an engine is blocked, logged out, or returns poor results.
---

# web-search

Search the web by driving AIApp's `WebBrowserTool` against multiple search engines, falling back automatically when one engine is blocked, logged out, or returns poor results. No search API keys are required — every engine is reached through the in-app browser.

> **Always spawn a sub-agent (secondary model) to perform the browsing.** `WebBrowserTool` is verbose and iterative — navigating, reading, and falling back across engines floods the main conversation. Delegate the entire search-and-read loop to a sub-agent and return only the final result and its source. Never drive `WebBrowserTool` directly from the main thread.

## When to use

Activate this skill when the user wants:
- real-time web results instead of model memory
- to find an official site, original page, or source for a claim
- a high-quality synthesized answer with citations
- privacy-oriented search
- resilient search that survives one engine being blocked

## Engines

| Engine | URL pattern | Strength | Login |
|---|---|---|---|
| Perplexity | `https://www.perplexity.ai/search?q={query}` | Highest answer quality, citations | Once, via `useAccounts` |
| Google | `https://www.google.com/search?q={query}` | Best general coverage, original pages | None |
| Bing | `https://www.bing.com/search?q={query}` | Good coverage + AI summary block | None |
| Brave | `https://search.brave.com/search?q={query}` | Privacy-friendly independent index | None |
| DuckDuckGo | `https://html.duckduckgo.com/html/?q={query}` | Lightweight privacy search, minimal HTML | None |

## Intent-based fallback chains

Pick the chain by user intent (or run `scripts/build_search_plan.py` to generate it):

- **Deep research / comparison / synthesized answer**: `Perplexity → Bing → Google → Brave`
- **General web / official site / source lookup**: `Google → Bing → Brave → DuckDuckGo`
- **Privacy-first**: `Brave → DuckDuckGo → Bing`

## Workflow

1. Infer the search intent from the request and pick the matching chain. Optionally run `scripts/build_search_plan.py "<query>" -i <deep|web|privacy> -j` to get the ordered URLs and block signals.
2. **Spawn a sub-agent on the secondary model to do the browsing** — `WebBrowserTool` is verbose and iterative, so isolate it from the main conversation (this matches the tool's own guidance).
3. Navigate `WebBrowserTool` to the first engine's URL.
4. Read results with the **`getText` action** — it returns only rendered visible text and is far lighter on tokens than `getHtml`. Reserve `getHtml` for when CSS selectors are needed to click into a specific result, and `findButtons` / `clickElementByText` to interact.
5. Check success criteria (below). If the page is blocked or unhelpful, advance to the next engine in the chain.
6. Return the answer **with its sources**. Every result must include the source URL(s) it came from — the page(s) actually opened or the result links cited. Never return a bare answer without attribution; if a claim cannot be traced to a source page, say so. Add a second independent source when cross-checking matters.

## Reading results efficiently

Default to the `getText` action for result pages — search results are text, so visible text is all that is needed and it keeps context small. Only switch to `getHtml` when a result must be clicked and a precise CSS selector is required. The skill is designed around `getText`-first reading.

## Perplexity login

Perplexity needs a signed-in session for best results. If the user has a connected Perplexity account, pass its connection ID via `WebBrowserTool`'s `useAccounts` argument (e.g. `["perplexity.ai/<account>"]`) so cookies are injected before navigation. If no account is connected or the session is expired, treat it as a fallback trigger and move to Google.

## Fallback rules

Switch to the next engine immediately when any of these occur:
- login expired or sign-in wall
- captcha / "unusual traffic" / "are you a robot" / "verify you are human" / "access denied"
- empty result page or redirect back to the engine home page
- only a search box is visible with no actual results
- extracted text is broken and yields no useful content

## Success criteria

Treat a search as successful when at least two are true:
- the URL or page text clearly indicates a result page (not the home page)
- extracted text is non-empty and contains meaningful results
- structured answers, a result list, or citations are present

## Resources

- `scripts/build_search_plan.py` — generate the engine order, pre-built URLs, and block signals for a query and intent.
- `references/routing-evals.json` — expected fallback chain per intent; consult when verifying or tuning routing.

## Notes

- Prefer Perplexity for synthesized, cited answers when a session is available.
- Prefer Google / Bing for finding original pages and official sites.
- Use Brave / DuckDuckGo as privacy-oriented backups.
- Never rely on a single engine — fallback is part of the design.
