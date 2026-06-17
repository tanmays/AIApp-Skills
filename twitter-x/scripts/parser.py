"""Translate raw Twitter/X GraphQL JSON into the skill's typed models.

The GraphQL responses are deeply nested and have shifted shape over time (most
notably name/screen_name moving from `legacy` to `core`). Everything here is
defensive: missing keys yield empty values rather than raising, so a single odd
entry never aborts a whole timeline parse.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from .models import Author, Metrics, Tweet, TweetMedia, UserProfile

logger = logging.getLogger(__name__)


# ── Utility helpers ──────────────────────────────────────────────────────

def _deep_get(data: Any, *keys: Any) -> Any:
	"""Walk nested dicts/lists by key. Integer keys index into lists.

	Returns None the moment a key is missing or a type doesn't match, so long
	access chains stay safe on partial responses.
	"""
	current = data
	for key in keys:
		if isinstance(key, int):
			if isinstance(current, list) and 0 <= key < len(current):
				current = current[key]
			else:
				return None
		elif isinstance(current, dict):
			current = current.get(key)
		else:
			return None
	return current


def _parse_int(value: Any, default: int = 0) -> int:
	"""Best-effort int conversion that tolerates commas and float strings."""
	try:
		text = str(value).replace(",", "").strip()
		if not text:
			return default
		return int(float(text))
	except (TypeError, ValueError):
		return default


def _extract_cursor(content: Dict[str, Any]) -> Optional[str]:
	"""Return the Bottom pagination cursor from a timeline entry, if present."""
	if content.get("cursorType") == "Bottom":
		return content.get("value")
	return None


# ── Media / Author extraction ────────────────────────────────────────────

def _extract_media(legacy: Dict[str, Any]) -> List[TweetMedia]:
	"""Collect photo/video/GIF media from a tweet's legacy payload.

	For videos the highest-bitrate MP4 variant is chosen.
	"""
	media = []
	for item in _deep_get(legacy, "extended_entities", "media") or []:
		media_type = item.get("type", "")
		if media_type == "photo":
			media.append(TweetMedia(
				type="photo",
				url=item.get("media_url_https", ""),
				width=_deep_get(item, "original_info", "width"),
				height=_deep_get(item, "original_info", "height"),
			))
		elif media_type in {"video", "animated_gif"}:
			variants = item.get("video_info", {}).get("variants", [])
			mp4_variants = [v for v in variants if v.get("content_type") == "video/mp4"]
			mp4_variants.sort(key=lambda v: v.get("bitrate", 0), reverse=True)
			media.append(TweetMedia(
				type=media_type,
				url=mp4_variants[0]["url"] if mp4_variants else item.get("media_url_https", ""),
				width=_deep_get(item, "original_info", "width"),
				height=_deep_get(item, "original_info", "height"),
			))
	return media


def _extract_author(user_data: Dict[str, Any], user_legacy: Dict[str, Any]) -> Author:
	"""Build an Author, reading from `core` first and falling back to `legacy`."""
	user_core = user_data.get("core", {})
	return Author(
		id=user_data.get("rest_id", ""),
		name=(
			user_core.get("name")
			or user_legacy.get("name")
			or user_data.get("name", "Unknown")
		),
		screen_name=(
			user_core.get("screen_name")
			or user_legacy.get("screen_name")
			or user_data.get("screen_name", "unknown")
		),
		profile_image_url=(
			user_data.get("avatar", {}).get("image_url")
			or user_legacy.get("profile_image_url_https", "")
		),
		verified=bool(
			user_data.get("is_blue_verified") or user_legacy.get("verified", False)
		),
	)


# ── User parsing ─────────────────────────────────────────────────────────

def parse_user_result(user_data: Dict[str, Any]) -> Optional[UserProfile]:
	"""Parse a GraphQL user result into a UserProfile, or None if unavailable."""
	if user_data.get("__typename") == "UserUnavailable":
		return None
	legacy = user_data.get("legacy", {})
	core = user_data.get("core", {})
	if not legacy and not core:
		return None
	name = core.get("name") or legacy.get("name", "")
	screen_name = core.get("screen_name") or legacy.get("screen_name", "")
	return UserProfile(
		id=user_data.get("rest_id", ""),
		name=name,
		screen_name=screen_name,
		bio=legacy.get("description", ""),
		location=legacy.get("location", ""),
		url=_deep_get(legacy, "entities", "url", "urls", 0, "expanded_url") or "",
		followers_count=_parse_int(legacy.get("followers_count"), 0),
		following_count=_parse_int(legacy.get("friends_count"), 0),
		tweets_count=_parse_int(legacy.get("statuses_count"), 0),
		likes_count=_parse_int(legacy.get("favourites_count"), 0),
		verified=user_data.get("is_blue_verified", False) or legacy.get("verified", False),
		profile_image_url=legacy.get("profile_image_url_https", ""),
		created_at=core.get("created_at") or legacy.get("created_at", ""),
	)


# ── Tweet parsing ────────────────────────────────────────────────────────

def _unwrap_visibility(result: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
	"""Unwrap a TweetWithVisibilityResults envelope.

	Returns the inner tweet data and whether it is gated as subscriber-only.
	"""
	if result.get("__typename") == "TweetWithVisibilityResults" and result.get("tweet"):
		return result["tweet"], bool(result.get("tweetInterstitial"))
	return result, False


def parse_tweet_result(result: Dict[str, Any], depth: int = 0) -> Optional[Tweet]:
	"""Parse a single tweet result into a Tweet.

	Resolves retweets to their source, recurses one level into quoted tweets,
	and prefers note_tweet full text for long-form posts. `depth` guards against
	pathological nesting.
	"""
	if depth > 2:
		return None

	tweet_data, is_subscriber_only = _unwrap_visibility(result)
	if tweet_data.get("__typename") == "TweetTombstone":
		return None

	legacy = tweet_data.get("legacy")
	core = tweet_data.get("core")
	if not isinstance(legacy, dict) or not isinstance(core, dict):
		return None

	user = _deep_get(core, "user_results", "result") or {}
	user_legacy = user.get("legacy", {})
	user_core = user.get("core", {})

	is_retweet = bool(_deep_get(legacy, "retweeted_status_result", "result"))
	actual_data = tweet_data
	actual_legacy = legacy
	actual_user = user
	actual_user_legacy = user_legacy
	retweet_subscriber_only = False

	if is_retweet:
		retweet_result = _deep_get(legacy, "retweeted_status_result", "result") or {}
		retweet_result, retweet_subscriber_only = _unwrap_visibility(retweet_result)
		retweet_legacy = retweet_result.get("legacy")
		retweet_core = retweet_result.get("core")
		if isinstance(retweet_legacy, dict) and isinstance(retweet_core, dict):
			actual_data = retweet_result
			actual_legacy = retweet_legacy
			actual_user = _deep_get(retweet_core, "user_results", "result") or {}
			actual_user_legacy = actual_user.get("legacy", {})

	media = _extract_media(actual_legacy)
	urls = [
		item.get("expanded_url", "")
		for item in _deep_get(actual_legacy, "entities", "urls") or []
	]
	quoted = _deep_get(actual_data, "quoted_status_result", "result")
	quoted_tweet = (
		parse_tweet_result(quoted, depth=depth + 1)
		if isinstance(quoted, dict)
		else None
	)
	author = _extract_author(actual_user, actual_user_legacy)

	retweeted_by = None
	if is_retweet:
		retweeted_by = (
			user_core.get("screen_name")
			or user_legacy.get("screen_name", "unknown")
		)

	note_text = _deep_get(
		actual_data, "note_tweet", "note_tweet_results", "result", "text"
	)

	return Tweet(
		id=actual_data.get("rest_id", ""),
		text=note_text or actual_legacy.get("full_text", ""),
		author=author,
		metrics=Metrics(
			likes=_parse_int(actual_legacy.get("favorite_count"), 0),
			retweets=_parse_int(actual_legacy.get("retweet_count"), 0),
			replies=_parse_int(actual_legacy.get("reply_count"), 0),
			quotes=_parse_int(actual_legacy.get("quote_count"), 0),
			views=_parse_int(_deep_get(actual_data, "views", "count"), 0),
			bookmarks=_parse_int(actual_legacy.get("bookmark_count"), 0),
		),
		created_at=actual_legacy.get("created_at", ""),
		media=media,
		urls=urls,
		is_retweet=is_retweet,
		retweeted_by=retweeted_by,
		quoted_tweet=quoted_tweet,
		lang=actual_legacy.get("lang", ""),
		is_subscriber_only=(
			(is_subscriber_only or retweet_subscriber_only)
			if is_retweet
			else is_subscriber_only
		),
	)


# ── Timeline response parsing ────────────────────────────────────────────

def parse_timeline_response(data: Any, get_instructions: Callable[[Any], Any]) -> Tuple[List[Tweet], Optional[str]]:
	"""Parse a timeline response into (tweets, next_cursor).

	`get_instructions` locates the timeline instructions for the specific
	endpoint, since each one nests them under a different path.
	"""
	tweets: List[Tweet] = []
	next_cursor: Optional[str] = None

	instructions = get_instructions(data)
	if not isinstance(instructions, list):
		logger.warning("No timeline instructions found")
		return tweets, next_cursor

	for instruction in instructions:
		entries = instruction.get("entries") or instruction.get("moduleItems") or []
		for entry in entries:
			content = entry.get("content", {})
			next_cursor = _extract_cursor(content) or next_cursor

			item_content = content.get("itemContent", {})
			result = _deep_get(item_content, "tweet_results", "result")
			if result:
				tweet = parse_tweet_result(result)
				if tweet:
					tweets.append(tweet)

			# Conversation/thread modules carry their tweets one level deeper.
			for nested_item in content.get("items", []):
				nested_result = _deep_get(
					nested_item, "item", "itemContent", "tweet_results", "result"
				)
				if nested_result:
					tweet = parse_tweet_result(nested_result)
					if tweet:
						tweets.append(tweet)

	return tweets, next_cursor
