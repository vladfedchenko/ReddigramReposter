"""This module contains a SubredditBrowser object. This object is intended to browse "top" section of a single subreddit
and repost its content to a Telegram community."""
import logging
import os
import praw
from prawcore.exceptions import ServerError
import re
from redis import Redis
from telegram.telegram_wrapper import TelegramWrapper, TelegramMediaType
from telegram.utils import TelegramHelper
import threading
import time
from typing import Tuple, Optional
from utils import DownloadManager


class SubredditBrowser:
    """This object is intended to browse a "top" section of a single subreddit and repost its content to a Telegram
    community."""

    def _browse_subreddit(self):
        logging.info("Subreddit browser thread started.")
        post = True
        last_post_time = time.time()
        while not self._browse_stop.is_set():
            if post:
                self._do_post_storage_cleanup()
                last_post_time = time.time()
                post = False
                try:
                    submissions = self._subreddit.top('day', limit=self._top_num)
                except ServerError:
                    logging.error("Reddit server error encountered. No reposts during this browse window.")
                    submissions = []
                for submission in submissions:
                    if not self._redis.sismember(f'{self._db_key_prefix}_posted', submission.id):
                        file_path, media_type = self._extract_media(submission)
                        if file_path is not None:
                            logging.debug(f'Reposting post ID: {submission.id} from {self._subreddit.display_name} '
                                          f'to {self._telegram_channel}.')

                            self._redis.sadd(f'{self._db_key_prefix}_posted', submission.id)
                            self._redis.hset(f'{self._db_key_prefix}_post_time', submission.id, time.time())
                            self._telegram_wrap.send_media_message(file_path,
                                                                   media_type,
                                                                   chat_title=self._telegram_channel,
                                                                   caption=submission.title)
                            # self._telegram_wrap.send_text_message(submission.title, chat_title=self._telegram_channel)
            else:
                if time.time() - last_post_time > self._browse_delay:
                    post = True
                else:
                    time.sleep(10)

    def _do_post_storage_cleanup(self):
        to_del = []
        for sub_id in self._redis.smembers(f'{self._db_key_prefix}_posted'):
            posted_time = float(self._redis.hget(f'{self._db_key_prefix}_post_time', sub_id))
            if time.time() - posted_time > self._cleanup_delay:
                to_del.append(sub_id)

        for sub_id in to_del:
            self._redis.srem(f'{self._db_key_prefix}_posted', sub_id)
            self._redis.hdel(f'{self._db_key_prefix}_post_time', sub_id)

    def _extract_media(self, submission: praw.models.Submission) -> Tuple[Optional[str], Optional[TelegramMediaType]]:
        download_url = None
        default_ext = None
        file_path = None
        logging.debug(f'Extracting media from submission: {submission}')
        if submission.url is not None:
            if submission.url.startswith('https://i.imgur.com'):
                if submission.url.endswith('gifv'):
                    media_id = re.findall(r'^https://i\.imgur\.com/(.+)\.gifv', submission.url)[0]
                    download_url = f'https://imgur.com/download/{media_id}'
                    default_ext = 'gif'
                    file_path = f'{self._tmp_dir}/{media_id}'
                elif submission.url.endswith('gif'):
                    media_id = re.findall(r'^https://i\.imgur\.com/(.+)\.gif', submission.url)[0]
                    download_url = f'https://i.imgur.com/{media_id}.gif'
                    default_ext = 'gif'
                    file_path = f'{self._tmp_dir}/{media_id}'
                elif submission.url.endswith('jpg'):
                    media_id = re.findall(r'^https://i\.imgur\.com/(.+)\.jpg', submission.url)[0]
                    download_url = f'https://i.imgur.com/{media_id}.jpg'
                    default_ext = 'jpg'
                    file_path = f'{self._tmp_dir}/{media_id}'
                elif submission.url.endswith('png'):
                    media_id = re.findall(r'^https://i\.imgur\.com/(.+)\.png', submission.url)[0]
                    download_url = f'https://i.imgur.com/{media_id}.png'
                    default_ext = 'png'
                    file_path = f'{self._tmp_dir}/{media_id}'

            elif submission.url.startswith('https://v.redd.it/'):
                if submission.media is not None and len(submission.media) > 0 and 'reddit_video' in submission.media \
                        and submission.media['reddit_video']['is_gif']:
                    # Reddit stores videos separately from the audio. For now, only gif-videos are reposted.
                    media_id = re.findall(r'^https://v\.redd\.it/(.+)', submission.url)[0]
                    download_url = submission.media['reddit_video']['fallback_url']
                    default_ext = 'mp4'
                    file_path = f'{self._tmp_dir}/{media_id}'

            elif submission.url.startswith('https://i.redd.it/'):
                media_id = re.findall(r'^https://i\.redd\.it/(.+)\.(\w+)', submission.url)[0][0]
                download_url = f'{submission.url}'
                default_ext = 'jpg'
                file_path = f'{self._tmp_dir}/{media_id}'

            elif submission.url.startswith('https://gfycat.com/'):
                if submission.url.endswith('gif'):
                    media_id = re.findall(r'^https://gfycat\.com/(.+)\.gif', submission.url)[0]
                    download_url = f'https://giant.gfycat.com/{media_id}.gif'
                    file_path = f'{self._tmp_dir}/{media_id}'
                    default_ext = 'gif'
        if download_url is not None:
            file_path = DownloadManager.download_media(download_url, file_path, default_ext)
            media_type = TelegramHelper.determine_media_type(file_path)
            return file_path, media_type
        return None, None

    # Cannot be static, multiple browser objects may subscribe to same TelegramWrapper object
    def _process_message_sent(self, message: dict):
        logging.debug(f"Message sent notification received: {message}")
        path = TelegramHelper.extract_media_path(message)
        if path is not None:
            os.remove(path)
        logging.debug(f"Message processed: {message}. File removed: {path}")

    def __del__(self):
        logging.debug(f"Deleting SubredditBrowser object.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def __init__(self,
                 reddit_creds: map,
                 subreddit_name: str,
                 telegram_wrap: TelegramWrapper,
                 telegram_channel: str,
                 redis_db: Redis,
                 top_num: int = 20,
                 browse_delay: int = 3600,  # one hour by default
                 cleanup_delay: int = 86400,  # one day by default
                 tmp_dir: str = 'tmp'):
        """Initialize SubredditBrowser object.

        Args:
            reddit_creds: A map of reddit credentials. Should contain: client_id, client_secret, password, username,
                user_agent. Visit https://reddit.com to obtain the credentials.
            subreddit_name: A subreddit to browse.
            telegram_wrap: Telegram client wrapper.
            redis_db: Redis DB instance. To store reposted posts IDs to avoid repost repetitions.
            telegram_channel: Name of the telegram channel to post into.
            top_num: Number of posts to queue on each update.
            browse_delay: Delay in seconds after which the subreddit will be browsed for updates.
            cleanup_delay: Delay in seconds after which old entries from DB are removed.
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

        self._redis = redis_db
        self._cleanup_delay = cleanup_delay
        self._db_key_prefix = f"{subreddit_name}_{telegram_channel}"

        self._browse_stop = threading.Event()
        self._browse_worker = threading.Thread(target=self._browse_subreddit, args=())
        self._browse_worker.start()

        self._tmp_dir = tmp_dir
        if not os.path.isdir(tmp_dir):
            os.makedirs(tmp_dir, exist_ok=True)

        self._telegram_wrap.subscribe_message_sent(self._process_message_sent)

    def is_running(self) -> bool:
        """Returns True is the subreddit browsing thread is running."""
        return not self._browse_stop.is_set()

    def stop(self):
        """Stop subreddit browsing thread."""
        logging.debug(f"Stopping SubredditBrowser object.")
        self._telegram_wrap.unsubscribe_message_sent(self._process_message_sent)
        if self._browse_stop is not None:
            self._browse_stop.set()
            self._browse_worker.join()
            self._browse_stop = None
            self._browse_worker = None
