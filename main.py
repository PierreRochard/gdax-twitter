from datetime import datetime, timedelta
from dateutil.tz import tzlocal
import pytz
import time

import requests
import matplotlib.dates as mdates
from matplotlib.dates import date2num
from matplotlib.finance import candlestick_ohlc
import matplotlib.pyplot as plt
from twython import Twython, TwythonError

from twitter_config import APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET

twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

exchange_api_url = 'https://api.exchange.coinbase.com/'


def calculate_granularity(delta):
    return int(delta.total_seconds()/200)


def output_graph(interval):
    fig1 = plt.figure()
    ax1 = fig1.add_subplot(111)

    end = datetime.now(tzlocal())
    if interval == 'month':
        delta = timedelta(days=30)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m - %-d'
        width = 0.008
    elif interval == 'week':
        delta = timedelta(days=7)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%a'
        width = 0.005
    elif interval == 'day':
        delta = timedelta(days=1)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-I:%M'
        width = 0.001
    elif interval == 'hour':
        delta = timedelta(minutes=60)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-I:%M'
        width = 0.00008
    else:
        return False
    params = {'granularity': granularity,
              'start': str(start),
              'end': str(end)}
    rates = requests.get(exchange_api_url + 'products/BTC-USD/candles', params=params).json()
    mkt_time = []
    mkt_low_price = []
    mkt_close_price = []
    mkt_high_price = []
    quotes = []
    for time, low, high, open_px, close, volume in rates:
        time = datetime.fromtimestamp(time, tz=pytz.utc).astimezone(tzlocal())
        mkt_time += [time]
        mkt_low_price += [float(low)]
        mkt_close_price += [float(close)]
        mkt_high_price += [float(high)]
        quotes += [(date2num(time), float(open_px), float(high), float(low), float(close))]

    plt.xlim(start, datetime.now(tzlocal()))

    candlestick_ohlc(ax1, quotes, width=width)

    myFmt = mdates.DateFormatter(datetime_format, tzlocal())
    plt.gca().xaxis.set_major_formatter(myFmt)
    plt.setp(plt.gca().get_xticklabels(), rotation=45, horizontalalignment='right')
    plt.savefig('{0}.png'.format(interval))


def generate_graphs(previous_tweet=False):
    while True:
        media_ids = []
        for interval in ['month', 'week', 'day', 'hour']:
            output_graph(interval)
            photo = open('{0}.png'.format(interval), 'rb')
            response = twitter.upload_media(media=photo)
            media_ids += [response['media_id']]
        if previous_tweet:
            twitter.destroy_status(id=previous_tweet['id_str'])
        try:
            previous_tweet = twitter.update_status(media_ids=media_ids)
        except TwythonError:
            print('TwythonError')
        time.sleep(60*5)


if __name__ == '__main__':
    now = datetime.now()
    minutes = int(now.strftime('%-M')) + 5
    while minutes % 5 != 0:
        time.sleep(1)
        now = datetime.now()
        minutes = int(now.strftime('%-M')) + 5
    generate_graphs(previous_tweet=False)
