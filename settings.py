"""This module contains al the settings required to start an instance of ReddigramReposter"""
# Telegram settings
tel_api_id = 0  # integer value, not string
tel_api_hash = ''
tel_phone = ''
tel_password = ''  # WARNING: password is stored without encryption. Make sure to secure the file.

tel_channel_name = ''

tel_db_dir = 'tdlib_db'
tel_log_file = 'tdlib.log'
tel_log_verbosity = 2  # WARNING level

# Reddit settings
red_client_id = ''
red_client_secret = ''
red_username = ''
red_password = ''  # WARNING: password is stored without encryption. Make sure to secure the file.
red_user_agent = ''

red_subreddit_name = ''
red_top_entries_num = 20
red_browse_delay = 3600  # sec
red_tmp_dir = 'tmp'

# General
log_location = 'reddigram_reposter.log'
log_format_str = '%(asctime)s - %(threadName)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
log_level = 30  # WARNING level
