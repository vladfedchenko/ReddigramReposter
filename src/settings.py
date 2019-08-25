"""This module contains all the settings required by an instance of ReddigramReposter"""
# Telegram settings
tel_channel_name = ''

tel_db_dir = None
tel_log_file = 'tdlib.log'
tel_log_verbosity = 2  # WARNING level

# Reddit settings
red_subreddit_name = ''
red_top_entries_num = 20
red_browse_delay = 3600  # sec
red_tmp_dir = 'tmp'

# General
log_location = 'reddigram_reposter.log'
log_format_str = '%(asctime)s - %(threadName)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
log_level = 30  # WARNING level

if tel_db_dir is None:
    tel_db_dir = "data/{}_{}_db".format(red_subreddit_name, tel_channel_name)
