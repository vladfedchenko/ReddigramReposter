"""This module contains a SubredditBrowser object. This object is intended to browse "top" section of a single subreddit
and repost its content to a Telegram community."""
import logging
import os
import praw
import re
from telegram.TelegramWrapper import TelegramWrapper, TelegramMediaType
import threading
import time
from typing import Tuple, Optional
from utils import DownloadManager


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
                for submission in submissions:
                    if submission.id not in self._posted_set:
                        self._posted_set.add(submission.id)
                        file_path, media_type = self._extract_media(submission)
                        self._clearance_queue.append((time.time(), file_path, submission.id))
                        if file_path is not None:
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
        i = 0
        for post_info in self._clearance_queue:
            if time.time() - post_info[0] > 25 * self._browse_delay:
                i += 1
            else:
                break

        to_del = self._clearance_queue[0:i]
        self._clearance_queue = self._clearance_queue[i:]

        for t, path, s_id in to_del:
            os.remove(path)
            self._posted_set.remove(s_id)

    def _extract_media(self, submission: praw.models.Submission) -> Tuple[Optional[str], Optional[TelegramMediaType]]:
        download_url = None
        default_ext = None
        file_path = None
        if submission.url is not None:
            if submission.url.startswith('http://i.imgur.com') or submission.url.startswith('https://i.imgur.com'):
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
                if len(submission.media) > 0 and 'reddit_video' in submission.media \
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
            media_type = TelegramWrapper.determine_media_type(file_path)
            return file_path, media_type
        return None, None

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
        self._browse_worker.start()

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
