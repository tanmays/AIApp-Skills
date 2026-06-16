#!/usr/bin/env python3
"""
build_search_plan.py - Build a multi-engine web search plan with automatic
fallback ordering, tailored for AIApp's WebBrowserTool.

This script does NOT touch the network. It only emits a plan: which engines to
try, in what order, the pre-built search URLs, and the signals that should
trigger a fallback to the next engine. The agent then drives WebBrowserTool
(getText / getHtml / findButtons / clickElementByText) against that plan.
"""

import argparse
import json
import urllib.parse
from typing import Dict, List

# English-language, browser-drivable engines only. Each loads a result page via
# a query-string URL, so WebBrowserTool can navigate directly with `getText`.
SOURCES: Dict[str, Dict] = {
	"perplexity": {
		"name": "Perplexity",
		"url": "https://www.perplexity.ai/search?q={query}",
		"strength": "Highest answer quality with citations",
		"needs_login": True,
	},
	"google": {
		"name": "Google",
		"url": "https://www.google.com/search?q={query}",
		"strength": "Best general web coverage; original pages and official sites",
		"needs_login": False,
	},
	"bing": {
		"name": "Bing",
		"url": "https://www.bing.com/search?q={query}",
		"strength": "Good coverage plus an AI summary block",
		"needs_login": False,
	},
	"brave": {
		"name": "Brave",
		"url": "https://search.brave.com/search?q={query}",
		"strength": "Privacy-friendly, independent index",
		"needs_login": False,
	},
	"duckduckgo": {
		"name": "DuckDuckGo",
		"url": "https://html.duckduckgo.com/html/?q={query}",
		"strength": "Lightweight privacy search; minimal HTML result page",
		"needs_login": False,
	},
}

# Intent -> ordered fallback chain. Try the first engine; on a block signal or a
# poor result, move to the next.
FALLBACK_CHAINS: Dict[str, List[str]] = {
	"deep": ["perplexity", "bing", "google", "brave"],
	"web": ["google", "bing", "brave", "duckduckgo"],
	"privacy": ["brave", "duckduckgo", "bing"],
	"general": ["google", "bing", "brave", "duckduckgo"],
}

# Substrings in extracted page text that indicate the engine blocked the request.
# Switch to the next engine in the chain when any of these appear.
BLOCK_SIGNS = [
	"captcha",
	"unusual traffic",
	"are you a robot",
	"verify you are human",
	"access denied",
	"detected unusual activity",
	"please try again later",
]


def build_url(source: str, query: str) -> str:
	encoded = urllib.parse.quote(query)
	return SOURCES[source]["url"].format(query=encoded)


def choose_chain(intent: str) -> List[str]:
	return FALLBACK_CHAINS.get(intent, FALLBACK_CHAINS["general"])


def make_plan(query: str, intent: str) -> Dict:
	chain = choose_chain(intent)
	steps = []
	for index, source in enumerate(chain, start=1):
		steps.append({
			"order": index,
			"source": source,
			"name": SOURCES[source]["name"],
			"url": build_url(source, query),
			"needs_login": SOURCES[source]["needs_login"],
			"strength": SOURCES[source]["strength"],
		})
	return {
		"query": query,
		"intent": intent,
		"fallback_chain": chain,
		"block_signs": BLOCK_SIGNS,
		"steps": steps,
		"success_rule": [
			"The page is a result page, not the engine home page",
			"Extracted text is non-empty and contains real results",
			"There are structured answers, a result list, or citations",
		],
		"tool_hint": (
			"For each step, navigate WebBrowserTool to `url` and read with the "
			"`getText` action (token-light). Use `getHtml` only when CSS selectors "
			"are needed to click into a result. If text contains any block_sign, "
			"advance to the next step."
		),
	}


def main():
	parser = argparse.ArgumentParser(description="Build a multi-engine web search plan")
	parser.add_argument("query", nargs="?", help="The search query")
	parser.add_argument("-i", "--intent", default="general", choices=list(FALLBACK_CHAINS.keys()), help="Search intent")
	parser.add_argument("-l", "--list", action="store_true", help="List all available engines")
	parser.add_argument("-j", "--json", action="store_true", help="Output the plan as JSON")
	args = parser.parse_args()

	if args.list:
		print("Available search engines:")
		for key, value in SOURCES.items():
			login = "login required" if value["needs_login"] else "no login"
			print(f"- {key}: {value['name']} ({login}) — {value['strength']}")
		return

	if not args.query:
		parser.print_help()
		return

	plan = make_plan(args.query, args.intent)
	if args.json:
		print(json.dumps(plan, ensure_ascii=False, indent=2))
		return

	print(f"Query:  {plan['query']}")
	print(f"Intent: {plan['intent']}")
	print("Fallback chain:")
	for step in plan["steps"]:
		login = "login required" if step["needs_login"] else "no login"
		print(f"  {step['order']}. {step['name']} ({login})")
		print(f"     {step['url']}")
	print("\nSwitch to the next engine when extracted text contains:")
	for sign in plan["block_signs"]:
		print(f"- {sign}")


if __name__ == "__main__":
	main()
