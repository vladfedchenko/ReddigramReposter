import logging
from reddit.subreddit_browser import SubredditBrowser
import secrets
import settings
from telegram.telegram_wrapper import TelegramWrapper
import time


def main():
    logging.basicConfig(filename=settings.log_location,
                        format=settings.log_format_str,
                        level=settings.log_level)

    with TelegramWrapper(tdlib_auth_info={'api_id': secrets.tel_api_id,
                                          'api_hash': secrets.tel_api_hash,
                                          'phone': secrets.tel_phone,
                                          'password': secrets.tel_password},
                         tdlib_database_directory=settings.tel_db_dir,
                         tdlib_log_file=settings.tel_log_file,
                         tdlib_log_verbosity=settings.tel_log_verbosity) as telegram:
        with SubredditBrowser(reddit_creds={'client_id': secrets.red_client_id,
                                            'client_secret': secrets.red_client_secret,
                                            'username': secrets.red_username,
                                            'password': secrets.red_password,
                                            'user_agent': secrets.red_user_agent},
                              subreddit_name=settings.red_subreddit_name,
                              telegram_wrap=telegram,
                              telegram_channel=settings.tel_channel_name,
                              top_num=settings.red_top_entries_num,
                              browse_delay=settings.red_browse_delay,
                              tmp_dir=settings.red_tmp_dir) as reddit:
            while reddit.is_running():
                time.sleep(10)


if __name__ == "__main__":
    main()
