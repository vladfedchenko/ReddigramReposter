"""This module contains all the objects required to collect statistics on reposted posts."""
import datetime
import logging
import os
from redis import Redis
from telegram.utils import TelegramHelper
from telegram.telegram_wrapper import TelegramMediaType
from typing import Dict, List, Tuple


class StatCollector:
    """This object collects statistics about reposted posts."""

    def _get_day_stats(self, day: str, db_suffix: str) -> Dict[str, float]:
        cur_key = f"{self._db_prefix}_date_{db_suffix}"
        cur_key_size = f"{self._db_prefix}_date_size_{db_suffix}"

        return self._get_totals_generic(cur_key, cur_key_size, f"{day}_")

    def _get_totals(self, db_suffix: str) -> Dict[str, float]:
        cur_key = f"{self._db_prefix}_total_{db_suffix}"
        cur_key_size = f"{self._db_prefix}_total_size_{db_suffix}"

        return self._get_totals_generic(cur_key, cur_key_size, "")

    def _get_totals_generic(self, cur_key: str, cur_key_size: str, cur_hkey_prefix: str) -> Dict[str, float]:
        res = {}

        total = 0
        total_size = 0
        for media_type in TelegramMediaType:
            cur_hkey = f"{cur_hkey_prefix}{media_type.name.lower()}"
            media_type_str = media_type.name.lower()

            val = self._get_val_if_exists(cur_key, cur_hkey)
            res[f'total_{media_type_str}'] = val
            total += val

            val = self._get_val_if_exists(cur_key_size, cur_hkey)
            res[f'total_{media_type_str}_size'] = val
            total_size += val

        res['total'] = total
        res['total_size'] = total_size

        return res

    def _get_val_if_exists(self, key: str, hkey: str) -> float:
        if not self._redis.hexists(key, hkey):
            return 0
        return float(self._redis.hget(key, hkey))

    def _get_week_stats(self, db_suffix: str) -> List[Tuple[str, Dict[str, float]]]:
        res = []
        start = datetime.date.today() - datetime.timedelta(days=6)
        today = datetime.date.today()

        while start <= today:
            day_str = str(start)
            res.append((day_str, self._get_day_stats(day_str, db_suffix)))

            start += datetime.timedelta(days=1)

        return res

    def _record_media_stats(self, file_path: str, db_suffix: str):

        def increment_hash_value(key: str, hkey: str, value):
            if not self._redis.hexists(key, hkey):
                self._redis.hset(key, hkey, 0)
            self._redis.hincrbyfloat(key, hkey, value)

        file_size = round(os.path.getsize(file_path) / 10 ** 6, 3)  # to megabyte
        media_type = TelegramHelper.determine_media_type(file_path).name.lower()
        today = str(datetime.date.today())

        logging.debug(f"Recording media statistics: type - {media_type}, size - {file_size}, date - {today}, "
                      f"action - {db_suffix}")

        # Total media reposted
        cur_key = f"{self._db_prefix}_total_{db_suffix}"
        increment_hash_value(cur_key, media_type, 1)

        # Total media size
        cur_key = f"{self._db_prefix}_total_size_{db_suffix}"
        increment_hash_value(cur_key, media_type, file_size)

        # Total media reposted today
        cur_key = f"{self._db_prefix}_date_{db_suffix}"
        cur_hkey = f"{today}_{media_type}"
        increment_hash_value(cur_key, cur_hkey, 1)

        # Total media size reposted today
        media_type = TelegramHelper.determine_media_type(file_path).name.lower()
        cur_key = f"{self._db_prefix}_date_size_{db_suffix}"
        cur_hkey = f"{today}_{media_type}"
        increment_hash_value(cur_key, cur_hkey, file_size)

    def __del__(self):
        logging.debug(f"Deleting StatCollector object.")
        self._redis = None
        logging.debug(f"StatCollector object deleted.")

    def __init__(self,
                 redis_db: Redis,
                 db_prefix: str):
        """Initialize StatCollector object
        Args:
            redis_db: Redis DB instance. To store reposted posts statistics.
            db_prefix: DB key prefix.
        """
        self._redis = redis_db
        self._db_prefix = db_prefix

    # Public methods
    def get_today_delivered(self) -> Dict[str, float]:
        """Get stats of delivered messages today.

        Returns:
            A dictionary containing next keys:
                'total'      - total number of messages delivered
                'total_size' - total size of delivered media.
                'total_[image|video|animation|document|audio]' - total number delivered by media type.
                'total_[image|video|animation|document|audio]_size' - total size delivered by media type.
        """
        logging.debug("Getting stats on delivered today messages")
        today = str(datetime.date.today())
        return self._get_day_stats(today, "delivered")

    def get_today_sent(self) -> Dict[str, float]:
        """Get stats of sent messages today.

        Returns:
            A dictionary containing next keys:
                'total'      - total number of messages sent
                'total_size' - total size of sent media.
                'total_[image|video|animation|document|audio]' - total number sent by media type.
                'total_[image|video|animation|document|audio]_size' - total size sent by media type.
        """
        logging.debug("Getting stats on sent today messages")
        today = str(datetime.date.today())
        return self._get_day_stats(today, "sent")

    def get_totals_delivered(self) -> Dict[str, float]:
        """Get total stats of delivered messages.

        Returns:
            A dictionary containing next keys:
                'total'      - total number of messages delivered
                'total_size' - total size of delivered media.
                'total_[image|video|animation|document|audio]' - total number delivered by media type.
                'total_[image|video|animation|document|audio]_size' - total size delivered by media type.
        """
        logging.debug("Getting stats on all delivered messages")
        return self._get_totals("delivered")

    def get_totals_sent(self) -> Dict[str, float]:
        """Get total stats of sent messages.

        Returns:
            A dictionary containing next keys:
                'total'      - total number of messages sent
                'total_size' - total size of sent media.
                'total_[image|video|animation|document|audio]' - total number sent by media type.
                'total_[image|video|animation|document|audio]_size' - total size sent by media type.
        """
        logging.debug("Getting stats on all sent messages")
        return self._get_totals("sent")

    def get_week_delivered(self) -> List[Tuple[str, Dict[str, float]]]:
        """Get stats of delivered messages last week.

        Returns:
            A list containing two element tuples:
                first - date string
                second - dict similar to one retrned by get_today_delivered
        """
        logging.debug("Getting stats on delivered this week messages")
        return self._get_week_stats("delivered")

    def get_week_sent(self) -> List[Tuple[str, Dict[str, float]]]:
        """Get stats of sent messages last week.

        Returns:
            A list containing two element tuples:
                first - date string
                second - dict similar to one retrned by get_today_sent
        """
        logging.debug("Getting stats on sent this week messages")
        return self._get_week_stats("sent")

    def record_media_delivered(self, file_path: str):
        """Record to the database all the statistics when the message has been delivered.
        Args:
            file_path: Path to the reposted media file.
        """
        self._record_media_stats(file_path, "delivered")

    def record_media_sent(self, file_path: str):
        """Record to the database all the statistics when the message has been sent.
        Args:
            file_path: Path to the reposted media file.
        """
        self._record_media_stats(file_path, "sent")
