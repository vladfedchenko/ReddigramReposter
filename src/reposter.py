"""This is an entry file for Flask ReddigramReposter app"""
from flask import Flask, redirect, render_template, request, url_for
import logging
import os
from reddit.subreddit_browser import SubredditBrowser
from redis import Redis
import secrets
import settings
from telegram.telegram_wrapper import TelegramWrapper, TelegramAuthState
import time

app = Flask("ReddigramReposter", root_path=os.path.dirname(__file__))

# logging setup
logging.basicConfig(filename=settings.log_location,
                    format=settings.log_format_str,
                    level=settings.log_level)

# redis init
logging.debug(f"Connecting to Redis instance at {secrets.redis_host}:{secrets.redis_port}")
redis = Redis(host=secrets.redis_host, port=secrets.redis_port, db=secrets.redis_db)
assert redis.ping()
logging.info(f"Connected to Redis instance at {secrets.redis_host}:{secrets.redis_port}")

# telegram init
telegram = None
reddit = None


@app.route('/')
def index():
    global telegram
    return render_template('index.html',
                           logged_in=telegram is not None,
                           subreddit=settings.red_subreddit_name,
                           tel_channel=settings.tel_channel_name)


@app.route('/login', methods=['GET', 'POST'])
def login():
    global telegram
    global reddit

    if request.method == 'POST':
        settings.red_subreddit_name = request.form.get("subreddit")
        settings.tel_channel_name = request.form.get("tel_channel")

        settings.tel_db_dir = "data/{}_{}_db".format(settings.red_subreddit_name, settings.tel_channel_name)

    if telegram is None:
        telegram = TelegramWrapper(tdlib_log_file=settings.tel_log_file,
                                   tdlib_log_verbosity=settings.tel_log_verbosity)

    while telegram.authentication_state != TelegramAuthState.READY:

        if telegram.authentication_state == TelegramAuthState.WAIT_TDLIB_PARAMETERS:
            telegram.set_tdlib_parameters(secrets.tel_api_id, secrets.tel_api_hash, settings.tel_db_dir)

        elif telegram.authentication_state == TelegramAuthState.WAIT_PHONE_NUMBER:
            telegram.set_tdlib_phone(secrets.tel_phone)

        elif telegram.authentication_state == TelegramAuthState.WAIT_MFA_CODE:
            return redirect(url_for('mfa_code'))

        elif telegram.authentication_state == TelegramAuthState.WAIT_PASSWORD:
            telegram.set_tdlib_password(secrets.tel_password)

        time.sleep(0.5)

    if reddit is None:
        telegram.update_chat_ids()
        time.sleep(1)
        reddit = SubredditBrowser(reddit_creds={'client_id': secrets.red_client_id,
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
                                  tmp_dir=settings.red_tmp_dir)

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    logging.debug(f"Logging out.")
    global reddit
    global telegram

    reddit.stop()
    telegram.stop()

    del reddit
    reddit = None

    del telegram
    telegram = None
    return redirect(url_for('index'))


@app.route('/mfa_code', methods=['GET', 'POST'])
def mfa_code():
    if request.method == 'POST':
        code = request.form['mfa']
        telegram.set_tdlib_mfa_code(code)
        return redirect(url_for('login'))
    else:
        return render_template('mfa.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)
