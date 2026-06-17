"""Command-line entry point for the twitter-x skill.

Authentication resolves in this order:
  1. Explicit flags: --auth-token / --ct0
  2. A connection cookie file: --cookies-file PATH (or $TWITTER_X_COOKIES_FILE)
  3. Auto-discovered cookie file under config/websites/x.com/<account>/cookies.json
  4. Environment fallback: $TWITTER_AUTH_TOKEN / $TWITTER_CT0

The cookie file is the app's connected-account format: a JSON array of cookie
objects, each with at least "name" and "value". The auth_token and ct0 cookies
are pulled out of that array.

Usage:
    python -m scripts.cli <command> [options]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

from .client import TwitterAPIError, TwitterClient
from .models import Tweet, UserProfile


# ── Cookie resolution ──────────────────────────────────────────────────────

def _read_cookie_pair(cookies_path: Path) -> Tuple[str, str]:
	"""Pull (auth_token, ct0) out of an app connection cookie file.

	The file is a JSON array of cookie objects ({"name": ..., "value": ...}),
	exactly as the app writes it to config/websites/<domain>/<account>/cookies.json.
	"""
	try:
		raw = json.loads(cookies_path.read_text(encoding="utf-8"))
	except (OSError, ValueError) as error:
		raise RuntimeError(f"Could not read cookie file {cookies_path}: {error}")

	by_name = {entry.get("name"): entry.get("value", "") for entry in raw if isinstance(entry, dict)}
	auth_token = by_name.get("auth_token", "")
	ct0 = by_name.get("ct0", "")
	if not auth_token or not ct0:
		raise RuntimeError(
			f"Cookie file {cookies_path} is missing auth_token and/or ct0. "
			"Re-authenticate the x.com connection in Settings → Connected Accounts."
		)
	return auth_token, ct0


def _discover_cookie_file(start: Optional[Path] = None) -> Optional[Path]:
	"""Search upward for a connected x.com account's cookies.json.

	Walks from the current directory toward the workspace root looking for
	config/websites/x.com/. With a single connected account its cookies.json is
	returned; with several, the caller is asked to pick one via --cookies-file.
	"""
	current = (start or Path.cwd()).resolve()
	for directory in [current, *current.parents]:
		x_dir = directory / "config" / "websites" / "x.com"
		if not x_dir.is_dir():
			continue
		account_files = sorted(
			account_dir / "cookies.json"
			for account_dir in x_dir.iterdir()
			if (account_dir / "cookies.json").is_file()
		)
		if len(account_files) == 1:
			return account_files[0]
		if len(account_files) > 1:
			accounts = ", ".join(path.parent.name for path in account_files)
			raise RuntimeError(
				f"Multiple x.com connections found ({accounts}). "
				"Pass --cookies-file to choose one."
			)
		return None
	return None


def _get_client(args: argparse.Namespace) -> TwitterClient:
	auth_token = getattr(args, "auth_token", None)
	ct0 = getattr(args, "ct0", None)
	if auth_token and ct0:
		return TwitterClient(auth_token=auth_token, ct0=ct0)

	cookies_file = getattr(args, "cookies_file", None) or os.environ.get("TWITTER_X_COOKIES_FILE")
	cookies_path = Path(cookies_file) if cookies_file else _discover_cookie_file()
	if cookies_path:
		auth_token, ct0 = _read_cookie_pair(cookies_path)
		return TwitterClient(auth_token=auth_token, ct0=ct0)

	auth_token = auth_token or os.environ.get("TWITTER_AUTH_TOKEN", "")
	ct0 = ct0 or os.environ.get("TWITTER_CT0", "")
	if auth_token and ct0:
		return TwitterClient(auth_token=auth_token, ct0=ct0)

	print(
		"Error: no x.com credentials found. Provide one of:\n"
		"  • --cookies-file config/websites/x.com/<account>/cookies.json\n"
		"  • --auth-token <value> --ct0 <value>\n"
		"  • $TWITTER_AUTH_TOKEN and $TWITTER_CT0\n"
		"Tip: connect an x.com account in Settings → Connected Accounts first.",
		file=sys.stderr,
	)
	sys.exit(1)


def _add_auth_args(parser: argparse.ArgumentParser) -> None:
	parser.add_argument("--cookies-file", metavar="PATH",
	                    help="Path to a connection cookies.json (auto-discovered when omitted)")
	parser.add_argument("--auth-token", metavar="TOKEN",
	                    help="x.com auth_token cookie (or set TWITTER_AUTH_TOKEN)")
	parser.add_argument("--ct0", metavar="CT0",
	                    help="x.com ct0 cookie (or set TWITTER_CT0)")


# ── Output helpers ──────────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
	if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
		return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
	if isinstance(obj, list):
		return [_to_dict(item) for item in obj]
	return obj


def _print_json(data: Any) -> None:
	print(json.dumps(_to_dict(data), ensure_ascii=False, indent=2))


def _print_tweets(tweets: List[Tweet], as_json: bool) -> None:
	if as_json:
		_print_json(tweets)
		return
	for tweet in tweets:
		retweet_tag = f"  [RT by @{tweet.retweeted_by}]" if tweet.is_retweet else ""
		subscriber_tag = " [subscriber only]" if tweet.is_subscriber_only else ""
		print(f"── @{tweet.author.screen_name}{retweet_tag}{subscriber_tag}  [{tweet.created_at}]")
		print(f"   {tweet.text[:280]}")
		metrics = tweet.metrics
		print(f"   ❤️ {metrics.likes}  🔁 {metrics.retweets}  💬 {metrics.replies}  👁 {metrics.views}  🔖 {metrics.bookmarks}")
		if tweet.quoted_tweet:
			quoted = tweet.quoted_tweet
			print(f"   ↳ QT @{quoted.author.screen_name}: {quoted.text[:120]}")
		if tweet.article_title:
			print(f"   📄 Article: {tweet.article_title}")
		if tweet.media:
			print(f"   📎 {len(tweet.media)} media item(s)")
		print()


def _print_users(users: List[UserProfile], as_json: bool) -> None:
	if as_json:
		_print_json(users)
		return
	for user in users:
		verified = " ✓" if user.verified else ""
		print(f"@{user.screen_name}{verified}  ({user.name})")
		print(f"  followers={user.followers_count}  following={user.following_count}  tweets={user.tweets_count}")
		if user.bio:
			print(f"  {user.bio[:120]}")
		print()


# ── Command handlers ───────────────────────────────────────────────────────

def cmd_feed(args: argparse.Namespace) -> None:
	client = _get_client(args)
	if args.type == "following":
		tweets = client.fetch_following_feed(count=args.max)
	else:
		tweets = client.fetch_home_timeline(count=args.max)
	_print_tweets(tweets, args.json)


def cmd_bookmarks(args: argparse.Namespace) -> None:
	client = _get_client(args)
	tweets = client.fetch_bookmarks(count=args.max)
	_print_tweets(tweets, args.json)


def cmd_bookmark_folders(args: argparse.Namespace) -> None:
	client = _get_client(args)
	folders = client.fetch_bookmark_folders()
	if args.json:
		_print_json(folders)
	else:
		for folder in folders:
			print(f"[{folder.id}] {folder.name}")


def cmd_search(args: argparse.Namespace) -> None:
	client = _get_client(args)
	tweets = client.fetch_search(args.query, count=args.max, product=args.tab)
	_print_tweets(tweets, args.json)


def cmd_user(args: argparse.Namespace) -> None:
	client = _get_client(args)
	user = client.fetch_user(args.screen_name)
	if args.json:
		_print_json(user)
	else:
		verified = " ✓" if user.verified else ""
		print(f"@{user.screen_name}{verified}  ({user.name})")
		print(f"  id={user.id}")
		print(f"  followers={user.followers_count}  following={user.following_count}  tweets={user.tweets_count}")
		if user.bio:
			print(f"  bio: {user.bio}")
		if user.location:
			print(f"  location: {user.location}")
		print(f"  joined: {user.created_at}")


def cmd_user_posts(args: argparse.Namespace) -> None:
	client = _get_client(args)
	user = client.fetch_user(args.screen_name)
	tweets = client.fetch_user_tweets(user.id, count=args.max)
	_print_tweets(tweets, args.json)


def cmd_user_likes(args: argparse.Namespace) -> None:
	client = _get_client(args)
	user = client.fetch_user(args.screen_name)
	tweets = client.fetch_user_likes(user.id, count=args.max)
	_print_tweets(tweets, args.json)


def cmd_tweet(args: argparse.Namespace) -> None:
	client = _get_client(args)
	tweet_id = args.tweet_id.rstrip("/").split("/")[-1]
	tweets = client.fetch_tweet_detail(tweet_id, count=args.max)
	_print_tweets(tweets, args.json)


def cmd_tweet_by_id(args: argparse.Namespace) -> None:
	client = _get_client(args)
	tweet_id = args.tweet_id.rstrip("/").split("/")[-1]
	tweet = client.fetch_tweet_by_id(tweet_id)
	if tweet is None:
		print(f"Tweet {tweet_id} not found.", file=sys.stderr)
		sys.exit(1)
	_print_tweets([tweet], args.json)


def cmd_list(args: argparse.Namespace) -> None:
	client = _get_client(args)
	tweets = client.fetch_list_timeline(args.list_id, count=args.max)
	_print_tweets(tweets, args.json)


def cmd_followers(args: argparse.Namespace) -> None:
	client = _get_client(args)
	users = client.fetch_followers(args.user_id, count=args.max)
	_print_users(users, args.json)


def cmd_following(args: argparse.Namespace) -> None:
	client = _get_client(args)
	users = client.fetch_following(args.user_id, count=args.max)
	_print_users(users, args.json)


def cmd_post(args: argparse.Namespace) -> None:
	client = _get_client(args)
	result = client.post_tweet(args.text, reply_to_id=getattr(args, "reply_to", None))
	tweet_id = (
		result.get("data", {}).get("create_tweet", {}).get("tweet_results", {})
		.get("result", {}).get("rest_id", "")
	)
	if tweet_id:
		print(f"Posted: https://x.com/i/web/status/{tweet_id}")
	else:
		print("Posted (no ID returned).")


def cmd_delete(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.delete_tweet(args.tweet_id)
	print(f"Deleted tweet {args.tweet_id}")


def cmd_like(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.like_tweet(args.tweet_id)
	print(f"Liked {args.tweet_id}")


def cmd_unlike(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.unlike_tweet(args.tweet_id)
	print(f"Unliked {args.tweet_id}")


def cmd_retweet(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.retweet(args.tweet_id)
	print(f"Retweeted {args.tweet_id}")


def cmd_unretweet(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.unretweet(args.tweet_id)
	print(f"Unretweeted {args.tweet_id}")


def cmd_bookmark(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.bookmark_tweet(args.tweet_id)
	print(f"Bookmarked {args.tweet_id}")


def cmd_unbookmark(args: argparse.Namespace) -> None:
	client = _get_client(args)
	client.unbookmark_tweet(args.tweet_id)
	print(f"Removed bookmark {args.tweet_id}")


# ── Argument parser ─────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(
		prog="twitter-x",
		description="Read and write Twitter/X data over the internal GraphQL API (cookie auth, stdlib only).",
	)
	subparsers = parser.add_subparsers(dest="command", metavar="<command>")
	subparsers.required = True

	feed = subparsers.add_parser("feed", help="Home timeline (For You or Following)")
	feed.add_argument("--type", choices=["for-you", "following"], default="for-you")
	feed.add_argument("--max", type=int, default=20, metavar="N")
	feed.add_argument("--json", action="store_true")
	_add_auth_args(feed)
	feed.set_defaults(func=cmd_feed)

	bookmarks = subparsers.add_parser("bookmarks", help="Saved bookmarks")
	bookmarks.add_argument("--max", type=int, default=50, metavar="N")
	bookmarks.add_argument("--json", action="store_true")
	_add_auth_args(bookmarks)
	bookmarks.set_defaults(func=cmd_bookmarks)

	bookmark_folders = subparsers.add_parser("bookmark-folders", help="List bookmark folders")
	bookmark_folders.add_argument("--json", action="store_true")
	_add_auth_args(bookmark_folders)
	bookmark_folders.set_defaults(func=cmd_bookmark_folders)

	search = subparsers.add_parser("search", help="Search tweets")
	search.add_argument("query", help="Search query")
	search.add_argument("--tab", choices=["Top", "Latest", "Photos", "Videos"], default="Top")
	search.add_argument("--max", type=int, default=20, metavar="N")
	search.add_argument("--json", action="store_true")
	_add_auth_args(search)
	search.set_defaults(func=cmd_search)

	user = subparsers.add_parser("user", help="User profile")
	user.add_argument("screen_name")
	user.add_argument("--json", action="store_true")
	_add_auth_args(user)
	user.set_defaults(func=cmd_user)

	user_posts = subparsers.add_parser("user-posts", help="Tweets posted by a user")
	user_posts.add_argument("screen_name")
	user_posts.add_argument("--max", type=int, default=20, metavar="N")
	user_posts.add_argument("--json", action="store_true")
	_add_auth_args(user_posts)
	user_posts.set_defaults(func=cmd_user_posts)

	user_likes = subparsers.add_parser("user-likes", help="Tweets liked by a user (own account only)")
	user_likes.add_argument("screen_name")
	user_likes.add_argument("--max", type=int, default=20, metavar="N")
	user_likes.add_argument("--json", action="store_true")
	_add_auth_args(user_likes)
	user_likes.set_defaults(func=cmd_user_likes)

	tweet = subparsers.add_parser("tweet", help="Tweet detail with reply thread")
	tweet.add_argument("tweet_id", help="Tweet ID or full URL")
	tweet.add_argument("--max", type=int, default=20, metavar="N")
	tweet.add_argument("--json", action="store_true")
	_add_auth_args(tweet)
	tweet.set_defaults(func=cmd_tweet)

	tweet_by_id = subparsers.add_parser("tweet-by-id", help="Fetch a single tweet by ID (no replies)")
	tweet_by_id.add_argument("tweet_id", help="Tweet ID or full URL")
	tweet_by_id.add_argument("--json", action="store_true")
	_add_auth_args(tweet_by_id)
	tweet_by_id.set_defaults(func=cmd_tweet_by_id)

	list_timeline = subparsers.add_parser("list", help="Twitter List timeline")
	list_timeline.add_argument("list_id")
	list_timeline.add_argument("--max", type=int, default=20, metavar="N")
	list_timeline.add_argument("--json", action="store_true")
	_add_auth_args(list_timeline)
	list_timeline.set_defaults(func=cmd_list)

	followers = subparsers.add_parser("followers", help="Followers of a user (requires user_id)")
	followers.add_argument("user_id")
	followers.add_argument("--max", type=int, default=20, metavar="N")
	followers.add_argument("--json", action="store_true")
	_add_auth_args(followers)
	followers.set_defaults(func=cmd_followers)

	following = subparsers.add_parser("following", help="Accounts a user follows (requires user_id)")
	following.add_argument("user_id")
	following.add_argument("--max", type=int, default=20, metavar="N")
	following.add_argument("--json", action="store_true")
	_add_auth_args(following)
	following.set_defaults(func=cmd_following)

	post = subparsers.add_parser("post", help="Post a new tweet or reply")
	post.add_argument("text")
	post.add_argument("--reply-to", metavar="TWEET_ID", dest="reply_to")
	_add_auth_args(post)
	post.set_defaults(func=cmd_post)

	delete = subparsers.add_parser("delete", help="Delete a tweet")
	delete.add_argument("tweet_id")
	_add_auth_args(delete)
	delete.set_defaults(func=cmd_delete)

	for name, handler in [("like", cmd_like), ("unlike", cmd_unlike)]:
		command = subparsers.add_parser(name, help=f"{'Like' if name == 'like' else 'Unlike'} a tweet")
		command.add_argument("tweet_id")
		_add_auth_args(command)
		command.set_defaults(func=handler)

	for name, handler in [("retweet", cmd_retweet), ("unretweet", cmd_unretweet)]:
		command = subparsers.add_parser(name, help=f"{'Retweet' if name == 'retweet' else 'Undo a retweet'}")
		command.add_argument("tweet_id")
		_add_auth_args(command)
		command.set_defaults(func=handler)

	for name, handler in [("bookmark", cmd_bookmark), ("unbookmark", cmd_unbookmark)]:
		command = subparsers.add_parser(name, help=f"{'Bookmark' if name == 'bookmark' else 'Remove a bookmark from'} a tweet")
		command.add_argument("tweet_id")
		_add_auth_args(command)
		command.set_defaults(func=handler)

	return parser


def main() -> None:
	parser = build_parser()
	args = parser.parse_args()
	try:
		args.func(args)
	except TwitterAPIError as error:
		print(f"API Error: {error}", file=sys.stderr)
		sys.exit(1)
	except RuntimeError as error:
		print(f"Error: {error}", file=sys.stderr)
		sys.exit(1)
	except KeyboardInterrupt:
		sys.exit(0)


if __name__ == "__main__":
	main()
