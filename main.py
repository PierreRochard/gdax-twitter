import argparse
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
import pytz
import time

import requests
import matplotlib.dates as mdates
from matplotlib.dates import date2num
from matplotlib.finance import candlestick_ohlc, volume_overlay
import matplotlib.pyplot as plt
from twython import Twython, TwythonError

from twitter_config import APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET

twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

exchange_api_url = 'https://api.exchange.coinbase.com/'

ARGS = argparse.ArgumentParser(description='Coinbase Exchange bot.')
ARGS.add_argument('--t', action='store_true', dest='tweeting', default=False, help='Tweet out graphs')

args = ARGS.parse_args()


def calculate_granularity(delta):
    return int(delta.total_seconds()/200)


def output_graph(interval):
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)

    end = datetime.now(tzlocal())
    if interval == 'year':
        title = 'Past Year'
        # Exchange hasn't been trading for a year (yet)
        delta = timedelta(days=30*8)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m'
        width = 0.008
        text = '\n12mos: '
    elif interval == 'month':
        title = 'Past Month'
        delta = timedelta(days=30)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m - %-d'
        width = 0.008
        text = '\n1mo: '
    elif interval == 'week':
        title = 'Past Week'
        delta = timedelta(days=7)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%a'
        width = 0.005
        text = '\nweek: '
    elif interval == 'day':
        title = 'Past Day'
        delta = timedelta(days=1)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-I:%M'
        width = 0.001
        text = '\nday: '
    else:
        return False
    params = {'granularity': granularity,
              'start': str(start),
              'end': str(end)}
    try:
        rates = requests.get(exchange_api_url + 'products/BTC-USD/candles', params=params).json()
    except ValueError:
        print('Unable to load Coinbase response')
    mkt_time = []
    mkt_open_price = []
    mkt_low_price = []
    mkt_close_price = []
    mkt_high_price = []
    volumes = []
    quotes = []
    for time, low, high, open_px, close, volume in rates:
        time = datetime.fromtimestamp(time, tz=pytz.utc).astimezone(tzlocal())
        mkt_time += [time]
        mkt_open_price += [float(open_px)]
        mkt_low_price += [float(low)]
        mkt_close_price += [float(close)]
        mkt_high_price += [float(high)]
        volumes += [float(volume)]
        quotes += [(date2num(time), float(open_px), float(high), float(low), float(close))]
    percent = round((mkt_close_price[0]-mkt_open_price[-1])*100/mkt_open_price[-1], 4)
    text += '{0:.2f} -> {1:.2f} {2:.2f}%'.format(mkt_open_price[-1], mkt_close_price[0], percent)
    plt.xlim(start, datetime.now(tzlocal()))

    red = (0.244, 0.102, 0.056)
    green = (0.132, 0.247, 0.102)

    candlestick_ohlc(ax1, quotes, width=width, colorup=green, colordown=red)
    # volume_overlay(ax1, opens=mkt_open_price, closes=mkt_close_price, volumes=volumes, colorup=green, colordown=red)
    myFmt = mdates.DateFormatter(datetime_format, tzlocal())
    plt.gca().xaxis.set_major_formatter(myFmt)
    plt.setp(plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
    plt.suptitle(title, fontsize=20)
    ax1.spines['right'].set_visible(False)
    ax1.spines['top'].set_visible(False)
    ax1.xaxis.set_ticks_position('bottom')
    ax1.yaxis.set_ticks_position('left')
    plt.savefig('{0}.png'.format(interval))
    return text


def generate_graphs(previous_tweet=False):
    while True:
        media_ids = []
        tweet = ''
        for interval in ['day', 'week', 'month', 'year']:
            tweet += output_graph(interval)
            if args.tweeting:
                photo = open('{0}.png'.format(interval), 'rb')
                response = twitter.upload_media(media=photo)
                media_ids += [response['media_id']]
        if previous_tweet and args.tweeting:
            twitter.destroy_status(id=previous_tweet['id_str'])
        if args.tweeting:
            try:
                previous_tweet = twitter.update_status(status=tweet, media_ids=media_ids)
            except TwythonError:
                print('TwythonError')
            time.sleep(60*10)
        else:
            return True


if __name__ == '__main__':
    if args.tweeting:
        now = datetime.now()
        minutes = int(now.strftime('%-M')) + 10
        while minutes % 10 != 0:
            time.sleep(1)
            now = datetime.now()
            minutes = int(now.strftime('%-M')) + 10
    generate_graphs(previous_tweet=False)
