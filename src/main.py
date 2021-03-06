import logging
from reddit.subreddit_browser import SubredditBrowser
from redis import Redis
import secrets
import settings
from telegram.telegram_wrapper import TelegramWrapper, TelegramAuthState
import time


def main():
    logging.basicConfig(filename=settings.log_location,
                        format=settings.log_format_str,
                        level=settings.log_level)

    logging.debug(f"Connecting to Redis instance at {secrets.redis_host}:{secrets.redis_port}")
    redis = Redis(host=secrets.redis_host, port=secrets.redis_port, db=secrets.redis_db)
    assert redis.ping()
    logging.info(f"Connected to Redis instance at {secrets.redis_host}:{secrets.redis_port}")

    with TelegramWrapper(tdlib_log_file=settings.tel_log_file,
                         tdlib_log_verbosity=settings.tel_log_verbosity) as telegram:

        while telegram.authentication_state != TelegramAuthState.READY:

            if telegram.authentication_state == TelegramAuthState.WAIT_TDLIB_PARAMETERS:
                telegram.set_tdlib_parameters(secrets.tel_api_id, secrets.tel_api_hash, settings.tel_db_dir)

            elif telegram.authentication_state == TelegramAuthState.WAIT_PHONE_NUMBER:
                telegram.set_tdlib_phone(secrets.tel_phone)

            elif telegram.authentication_state == TelegramAuthState.WAIT_MFA_CODE:
                mfa_code = input("Enter MFA code you received: ")
                telegram.set_tdlib_mfa_code(mfa_code)

            elif telegram.authentication_state == TelegramAuthState.WAIT_PASSWORD:
                telegram.set_tdlib_password(secrets.tel_password)

            time.sleep(0.5)

        with SubredditBrowser(reddit_creds={'client_id': secrets.red_client_id,
                                            'client_secret': secrets.red_client_secret,
                                            'username': secrets.red_username,
                                            'password': secrets.red_password,
                                            'user_agent': secrets.red_user_agent},
                              subreddit_name=settings.red_subreddit_name,
                              telegram_wrap=telegram,
                              telegram_channel=settings.tel_channel_name,
                              redis_db=redis,
                              top_num=settings.red_top_entries_num,
                              browse_delay=settings.red_browse_delay,
                              tmp_dir=settings.red_tmp_dir) as reddit:
            while reddit.is_running():
                time.sleep(10)


if __name__ == "__main__":
    main()
