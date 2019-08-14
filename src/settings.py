"""This module contains all the settings required by an instance of ReddigramReposter"""
# Telegram settings
tel_channel_name = 'VladTestChannel'

tel_db_dir = 'tdlib_db'
tel_log_file = 'tdlib.log'
tel_log_verbosity = 2  # WARNING level

# Reddit settings
red_subreddit_name = 'gifs'
red_top_entries_num = 20
red_browse_delay = 3600  # sec
red_tmp_dir = 'tmp'

# General
log_location = 'reddigram_reposter.log'
log_format_str = '%(asctime)s - %(threadName)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
log_level = 30  # WARNING level
