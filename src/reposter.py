"""This is an entry file for Flask ReddigramReposter app"""
from flask import Flask, redirect, render_template, request, url_for, abort
import json
import logging
import os
from reddit.subreddit_browser import SubredditBrowser
from redis import Redis
import secrets
import settings as app_settings
from stats import StatCollector, DataExtractor, BY_TYPE_KEYS, BY_TYPE_SIZE_KEYS
from telegram.telegram_wrapper import TelegramWrapper, TelegramAuthState
import time

app_root = os.path.dirname(__file__)
app = Flask("ReddigramReposter", root_path=app_root, static_folder=f'{app_root}/static')

# logging setup
logging.basicConfig(filename=app_settings.log_location,
                    format=app_settings.log_format_str,
                    level=app_settings.log_level)

# redis init
logging.debug(f"Connecting to Redis instance at {secrets.redis_host}:{secrets.redis_port}")
redis = Redis(host=secrets.redis_host, port=secrets.redis_port, db=secrets.redis_db)
assert redis.ping()
logging.info(f"Connected to Redis instance at {secrets.redis_host}:{secrets.redis_port}")

# telegram init
telegram = None
stat_collector = None
reddit = None


@app.route('/')
def index():
    global telegram
    global stat_collector

    today_stats_dict = None
    totals_stats_dict = None
    week_stats_dict = None

    if stat_collector is not None:

        # Today statistics extraction
        today_sent = stat_collector.get_today_sent()
        today_sent_list = [['Type', f'Number sent']] + DataExtractor.extract_media_by_type(today_sent)

        today_delivered = stat_collector.get_today_delivered()
        today_delivered_list = [['Type', f'Number delivered']] + \
            DataExtractor.extract_media_by_type(today_delivered)

        today_sent_size_list = [['Type', 'Size of sent']] + DataExtractor.extract_media_by_type_size(today_sent)

        today_delivered_size_list = [['Type', 'Size of delivered']] + \
            DataExtractor.extract_media_by_type_size(today_delivered)

        today_sent_delivered = [['Type', 'Number'],
                                ['Sent', today_sent['total']],
                                ['Delivered', today_delivered['total']]]

        today_sent_delivered_size = [['Type', 'Number'],
                                     ['Sent', today_sent['total_size']],
                                     ['Delivered', today_delivered['total_size']]]

        today_stats_dict = {'today_by_type_sent': json.dumps(today_sent_list),
                            'today_by_type_delivered': json.dumps(today_delivered_list),
                            'today_by_type_size_sent': json.dumps(today_sent_size_list),
                            'today_by_type_size_delivered': json.dumps(today_delivered_size_list),
                            'today_sent_delivered': json.dumps(today_sent_delivered),
                            'today_sent_delivered_size': json.dumps(today_sent_delivered_size)}

        # Week stats extraction
        week_sent = stat_collector.get_week_sent()
        week_delivered = stat_collector.get_week_delivered()

        week_sent_list = [['Day'] + [BY_TYPE_KEYS[key] for key in BY_TYPE_KEYS]]
        week_sent_list += DataExtractor.extract_multiday_media_by_type(week_sent)

        week_sent_size_list = [['Day'] + [BY_TYPE_SIZE_KEYS[key] for key in BY_TYPE_SIZE_KEYS]]
        week_sent_size_list += DataExtractor.extract_multiday_media_by_type_size(week_sent)

        week_delivered_list = [['Day'] + [BY_TYPE_KEYS[key] for key in BY_TYPE_KEYS]]
        week_delivered_list += DataExtractor.extract_multiday_media_by_type(week_delivered)

        week_delivered_size_list = [['Day'] + [BY_TYPE_SIZE_KEYS[key] for key in BY_TYPE_SIZE_KEYS]]
        week_delivered_size_list += DataExtractor.extract_multiday_media_by_type_size(week_delivered)

        week_stats_dict = {'week_sent': json.dumps(week_sent_list),
                           'week_sent_size': json.dumps(week_sent_size_list),
                           'week_delivered': json.dumps(week_delivered_list),
                           'week_delivered_size': json.dumps(week_delivered_size_list)}

        # Totals statistics extraction
        totals_sent = stat_collector.get_totals_sent()
        totals_sent_list = [['Type', f'Number sent']] + DataExtractor.extract_media_by_type(totals_sent)

        totals_delivered = stat_collector.get_totals_delivered()
        totals_delivered_list = [['Type', f'Number delivered']] + \
            DataExtractor.extract_media_by_type(totals_delivered)

        totals_sent_size_list = [['Type', 'Size of sent']] + DataExtractor.extract_media_by_type_size(totals_sent)

        totals_delivered_size_list = [['Type', 'Size of delivered']] + \
            DataExtractor.extract_media_by_type_size(totals_delivered)

        totals_sent_delivered = [['Type', 'Number'],
                                 ['Sent', totals_sent['total']],
                                 ['Delivered', totals_delivered['total']]]

        totals_sent_delivered_size = [['Type', 'Number'],
                                      ['Sent', totals_sent['total_size']],
                                      ['Delivered', totals_delivered['total_size']]]

        totals_stats_dict = {'totals_by_type_sent': json.dumps(totals_sent_list),
                             'totals_by_type_delivered': json.dumps(totals_delivered_list),
                             'totals_by_type_size_sent': json.dumps(totals_sent_size_list),
                             'totals_by_type_size_delivered': json.dumps(totals_delivered_size_list),
                             'totals_sent_delivered': json.dumps(totals_sent_delivered),
                             'totals_sent_delivered_size': json.dumps(totals_sent_delivered_size)}

    return render_template('index.html',
                           logged_in=telegram is not None,
                           subreddit=app_settings.red_subreddit_name,
                           tel_channel=app_settings.tel_channel_name,
                           today_stats_dict=today_stats_dict,
                           week_stats_dict=week_stats_dict,
                           totals_stats_dict=totals_stats_dict)


@app.route('/login', methods=['GET', 'POST'])
def login():
    global telegram
    global stat_collector
    global reddit
    global redis

    if request.method == 'POST':
        app_settings.red_subreddit_name = request.form.get("subreddit")
        app_settings.tel_channel_name = request.form.get("tel_channel")

        app_settings.tel_db_dir = "data/{}_{}_db".format(app_settings.red_subreddit_name, app_settings.tel_channel_name)

    if telegram is None:
        telegram = TelegramWrapper(tdlib_log_file=app_settings.tel_log_file,
                                   tdlib_log_verbosity=app_settings.tel_log_verbosity)

    while telegram.authentication_state != TelegramAuthState.READY:

        if telegram.authentication_state == TelegramAuthState.WAIT_TDLIB_PARAMETERS:
            telegram.set_tdlib_parameters(secrets.tel_api_id, secrets.tel_api_hash, app_settings.tel_db_dir)

        elif telegram.authentication_state == TelegramAuthState.WAIT_PHONE_NUMBER:
            telegram.set_tdlib_phone(secrets.tel_phone)

        elif telegram.authentication_state == TelegramAuthState.WAIT_MFA_CODE:
            return redirect(url_for('mfa_code'))

        elif telegram.authentication_state == TelegramAuthState.WAIT_PASSWORD:
            telegram.set_tdlib_password(secrets.tel_password)

        time.sleep(0.5)

    if stat_collector is None:
        stat_collector = StatCollector(redis, f"{app_settings.red_subreddit_name}_{app_settings.tel_channel_name}")

    if reddit is None:
        telegram.update_chat_ids()
        time.sleep(1)
        reddit = SubredditBrowser(reddit_creds={'client_id': secrets.red_client_id,
                                                'client_secret': secrets.red_client_secret,
                                                'username': secrets.red_username,
                                                'password': secrets.red_password,
                                                'user_agent': secrets.red_user_agent},
                                  subreddit_name=app_settings.red_subreddit_name,
                                  telegram_wrap=telegram,
                                  telegram_channel=app_settings.tel_channel_name,
                                  redis_db=redis,
                                  stat_collector=stat_collector,
                                  top_num=app_settings.red_top_entries_num,
                                  browse_delay=app_settings.red_browse_delay,
                                  tmp_dir=app_settings.red_tmp_dir)

    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    logging.debug(f"Logging out.")
    global reddit
    global telegram
    global stat_collector

    reddit.stop()
    telegram.stop()

    del reddit
    reddit = None

    del stat_collector
    stat_collector = None

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


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    global reddit
    if reddit is None:
        logging.error(f"Cannot change settings before login.")
        abort(503)

    if request.method == 'POST':
        reddit.top_entries = int(request.form['top_entries'])
        reddit.browse_delay = int(request.form['browse_delay'])

    return render_template('settings.html',
                           method_post=request.method == 'POST',
                           logged_in=True,
                           top_entries=reddit.top_entries,
                           browse_delay=reddit.browse_delay)


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
