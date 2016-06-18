import argparse
from datetime import datetime, timedelta
from pprint import pformat
import sys

from dateutil.tz import tzlocal
import pytz
import time

import requests
import matplotlib.dates as mdates
from matplotlib.dates import date2num
from matplotlib.finance import candlestick_ohlc
import matplotlib.pyplot as plt
from twython import Twython, TwythonError

from twitter_config import KEYS

exchange_api_url = 'https://api.gdax.com/'

ARGS = argparse.ArgumentParser(description='GDAX price tweeting bot.')
ARGS.add_argument('--t', action='store_true', dest='tweeting', default=False, help='Tweet out graphs')

args = ARGS.parse_args()


def calculate_granularity(delta):
    return int(delta.total_seconds() / 200)


def output_graph(interval, pair_config):
    pair = pair_config['from_currency'] + '-' + pair_config['to_currency']
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)

    end = datetime.now(tzlocal())
    if interval == 'year':
        title = 'Past 12 Months'
        delta = timedelta(weeks=48)
        start = end - delta
        granularity = calculate_granularity(end - start)
        datetime_format = '%m'
        width = 0.008
        text = '\n1y: '
    elif interval == 'month':
        title = 'Past Month'
        delta = timedelta(weeks=4)
        start = end - delta
        granularity = calculate_granularity(end - start)
        datetime_format = '%m - %d'
        width = 0.008
        text = '\n1m: '
    elif interval == 'week':
        title = 'Past Week'
        delta = timedelta(weeks=1)
        start = end - delta
        granularity = calculate_granularity(end - start)
        datetime_format = '%a'
        width = 0.005
        text = '\n1w: '
    elif interval == 'day':
        title = 'Past Day'
        delta = timedelta(days=1)
        start = end - delta
        granularity = calculate_granularity(end - start)
        datetime_format = '%I:%M'
        width = 0.001
        text = '\n1d: '
    else:
        return False
    params = {'granularity': granularity,
              'start': str(start),
              'end': str(end)}
    try:
        rates = requests.get(exchange_api_url + 'products/' + pair + '/candles', params=params).json()
    except ValueError:
        print('Unable to load GDAX response')
        return False
    if 'message' in rates and rates['message'].startswith('You have exceeded your request rate'):
        print('Requesting too fast')
        return False
    mkt_time = []
    mkt_open_price = []
    mkt_low_price = []
    mkt_close_price = []
    mkt_high_price = []
    volumes = []
    quotes = []
    vwap_multiple_sum = 0.0
    try:
        for timestamp, low, high, open_px, close, volume in rates:
            vwap_multiple_sum += float(close) * float(volume)
            timestamp = datetime.fromtimestamp(timestamp, tz=pytz.utc).astimezone(tzlocal())
            mkt_time += [timestamp]
            mkt_open_price += [float(open_px)]
            mkt_low_price += [float(low)]
            mkt_close_price += [float(close)]
            mkt_high_price += [float(high)]
            volumes += [float(volume)]
            quotes += [(date2num(timestamp), float(open_px), float(high), float(low), float(close))]
    except ValueError:
        print(pformat(rates))
        sys.exit(0)
    vwap = vwap_multiple_sum/sum(volumes)
    percent = round((mkt_close_price[0] - mkt_open_price[-1]) * 100 / mkt_open_price[-1], 4)
    text += '{0:.0f} -> {1:.0f} {2:.0f}%'.format(mkt_open_price[-1], mkt_close_price[0], percent)
    plt.xlim(start, datetime.now(tzlocal()))
    hl_percent = round((max(mkt_high_price) - min(mkt_low_price)) * 100 / min(mkt_low_price), 4)
    s = '''Open:{0:.2f} Close:{1:.2f}  {2:.2f}% \n Low:{3:.2f}  High:{4:.2f}   {5:.2f}%'''.format(mkt_open_price[-1],
                                                          mkt_close_price[0],
                                                          percent,
                                                          min(mkt_low_price),
                                                          max(mkt_high_price),
                                                          hl_percent)
    ax1.text(0.3, 0.9, s, transform=ax1.transAxes)

    red = (0.244, 0.102, 0.056)
    green = (0.132, 0.247, 0.102)
    candlestick_ohlc(ax1, quotes, width=width, colorup=green, colordown=red)
    # volume_overlay(ax1, opens=mkt_open_price, closes=mkt_close_price, volumes=volumes, colorup=green, colordown=red)
    date_formatter = mdates.DateFormatter(datetime_format, tzlocal())
    plt.gca().xaxis.set_major_formatter(date_formatter)
    plt.setp(plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
    plt.suptitle(title, fontsize=20)
    plt.gca().set_ylim([min(vwap*0.9, min(mkt_low_price)), max(vwap*1.1, max(mkt_high_price))])
    ax1.spines['right'].set_visible(False)
    ax1.spines['top'].set_visible(False)
    ax1.xaxis.set_ticks_position('bottom')
    ax1.yaxis.set_ticks_position('left')
    plt.savefig('{0}-{1}.png'.format(interval, pair_config['screen_name']))
    return text


def generate_graphs():
    for pair_config in KEYS:
        media_ids = []
        tweet = ''
        for interval in ['day', 'week', 'month', 'year']:
            text = output_graph(interval, pair_config)
            if not text:
                continue
            tweet += text
            if args.tweeting and pair_config['APP_KEY']:
                twitter = Twython(pair_config['APP_KEY'], pair_config['APP_SECRET'],
                                  pair_config['OAUTH_TOKEN'], pair_config['OAUTH_TOKEN_SECRET'])
                photo = open('{0}-{1}.png'.format(interval, pair_config['screen_name']), 'rb')
                try:
                    response = twitter.upload_media(media=photo)
                except TwythonError as err:
                    print('{0}'.format(err))
                    return True
                media_ids += [response['media_id']]
            time.sleep(10)
        if args.tweeting and pair_config['APP_KEY']:
            twitter = Twython(pair_config['APP_KEY'], pair_config['APP_SECRET'],
                            pair_config['OAUTH_TOKEN'], pair_config['OAUTH_TOKEN_SECRET'])
            try:
                for status in twitter.get_user_timeline(screen_name=pair_config['screen_name']):
                    twitter.destroy_status(id=status['id_str'])
                twitter.update_status(status=tweet, media_ids=media_ids)
            except TwythonError as err:
                print('{0}'.format(err))
                print(len(tweet))

if __name__ == '__main__':
    generate_graphs()
