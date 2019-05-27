"""This module contains a SubredditBrowser object. This object is intended to browse "top" section of a single subreddit
and repost its content to a Telegram community."""
import logging
import os
import praw
from telegram.TelegramWrapper import TelegramWrapper
import threading
import time


class SubredditBrowser:
    """This object is intended to browse a "top" section of a single subreddit and repost its content to a Telegram
    community."""
    _subreddit = None
    _telegram_wrap = None
    _telegram_channel = None
    _top_num = None
    _browse_delay = None
    _posted_set = None
    _clearance_queue = None

    _browse_worker = None
    _browse_stop = None

    _tmp_dir = None

    def _browse_subreddit(self):
        logging.info("Subreddit browser thread started.")
        post = True
        last_post_time = time.time()
        while not self._browse_stop.is_set():
            if post:
                self._do_post_storage_cleanup()
                last_post_time = time.time()
                post = False
                submissions = self._subreddit.top('day', limit=self._top_num)
                # TODO: browse subreddit and post to telegram
            else:
                if time.time() - last_post_time > self._browse_delay:
                    post = True
                else:
                    time.sleep(1)

    def _do_post_storage_cleanup(self):
        # TODO: clean posted set, remove created files
        pass

    def __init__(self,
                 reddit_creds: map,
                 subreddit_name: str,
                 telegram_wrap: TelegramWrapper,
                 telegram_channel: str,
                 top_num: int = 20,
                 browse_delay: int = 3600,
                 tmp_dir: str = 'tmp'):
        """Initialize SubredditBrowser object.

        Args:
            reddit_creds: A map of reddit credentials. Should contain: client_id, client_secret, password, username,
                user_agent. Visit https://reddit.com to obtain the credentials.
            subreddit_name: A subreddit to browse.
            telegram_wrap: Telegram client wrapper.
            telegram_channel: Name of the telegram channel to post into.
            top_num: Number of posts to queue on each update.
            browse_delay: Delay in seconds after which the subreddit will be browsed for updates.
            tmp_dir: Path to a directory to store files temporarily. Warning: cleanup process removes all files from
                the directory.
        """
        logging.debug("Creating class SubredditBrowser object.")
        self._subreddit = praw.Reddit(client_id=reddit_creds['client_id'],
                                      client_secret=reddit_creds['client_secret'],
                                      password=reddit_creds['password'],
                                      username=reddit_creds['username'],
                                      user_agent=reddit_creds['user_agent']).subreddit(subreddit_name)
        logging.info("Reddit login OK.")

        self._telegram_wrap = telegram_wrap
        self._telegram_wrap.update_chat_ids()
        self._telegram_channel = telegram_channel

        self._top_num = top_num
        self._browse_delay = browse_delay

        self._posted_set = set([])
        self._clearance_queue = []

        self._browse_stop = threading.Event()
        self._browse_worker = threading.Thread(target=self._browse_subreddit, args=())
        self._browse_worker.run()

        self._tmp_dir = tmp_dir
        if not os.path.isdir(tmp_dir):
            os.makedirs(tmp_dir, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._browse_stop is not None:
            self.stop()

    def is_running(self) -> bool:
        """Returns True is the subreddit browsing thread is running."""
        return not self._browse_stop.is_set()

    def stop(self):
        """Stop subreddit browsing thread."""
        self._browse_stop.set()