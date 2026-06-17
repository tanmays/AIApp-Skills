"""Typed domain models for the twitter-x skill.

Plain dataclasses describing the slice of Twitter/X data this skill reads and
writes. They are intentionally stdlib-only and JSON-serialisable so the CLI can
emit them directly with `dataclasses.asdict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Author:
	"""The account that wrote a tweet."""
	id: str
	name: str
	screen_name: str
	profile_image_url: str = ""
	verified: bool = False


@dataclass
class Metrics:
	"""Engagement counters attached to a tweet."""
	likes: int = 0
	retweets: int = 0
	replies: int = 0
	quotes: int = 0
	views: int = 0
	bookmarks: int = 0


@dataclass
class TweetMedia:
	"""A single photo, video, or GIF attached to a tweet."""
	type: str  # "photo" | "video" | "animated_gif"
	url: str
	width: Optional[int] = None
	height: Optional[int] = None


@dataclass
class Tweet:
	"""A tweet, including retweet/quote context and optional article fields."""
	id: str
	text: str
	author: Author
	metrics: Metrics
	created_at: str
	media: List[TweetMedia] = field(default_factory=list)
	urls: List[str] = field(default_factory=list)
	is_retweet: bool = False
	lang: str = ""
	retweeted_by: Optional[str] = None
	quoted_tweet: Optional["Tweet"] = None
	score: Optional[float] = None
	article_title: Optional[str] = None
	article_text: Optional[str] = None
	is_subscriber_only: bool = False


@dataclass
class BookmarkFolder:
	"""A named bookmark folder."""
	id: str
	name: str


@dataclass
class UserProfile:
	"""A user's public profile."""
	id: str
	name: str
	screen_name: str
	bio: str = ""
	location: str = ""
	url: str = ""
	followers_count: int = 0
	following_count: int = 0
	tweets_count: int = 0
	likes_count: int = 0
	verified: bool = False
	profile_image_url: str = ""
	created_at: str = ""
