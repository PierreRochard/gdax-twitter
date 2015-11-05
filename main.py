import argparse
from datetime import datetime, timedelta, date
from dateutil.tz import tzlocal
import pytz
import time

import requests
import matplotlib.dates as mdates
from matplotlib.dates import date2num
from matplotlib.finance import candlestick_ohlc, volume_overlay
import matplotlib.pyplot as plt
from twython import Twython, TwythonError

from twitter_config import APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET, SCREEN_NAME

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
        start = date(2015, 4, 1)
        months = (end.year - start.year)*12 + end.month - start.month
        if months > 12:
            months = 12
        title = 'Past ' + str(months) + ' Months'
        delta = timedelta(weeks=4*months)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m'
        width = 0.008
        text = '\n8m: '
    elif interval == 'month':
        title = 'Past Month'
        delta = timedelta(weeks=4)
        start = end - delta
        granularity = calculate_granularity(end-start)
        datetime_format = '%-m - %-d'
        width = 0.008
        text = '\n1m: '
    elif interval == 'week':
        title = 'Past Week'
        delta = timedelta(weeks=1)
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
        return False
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
    text += '{0:.0f} -> {1:.0f} {2:.0f}%'.format(mkt_open_price[-1], mkt_close_price[0], percent)
    plt.xlim(start, datetime.now(tzlocal()))
    hl_percent = round((max(mkt_high_price)-min(mkt_low_price))*100/min(mkt_low_price), 4)
    s = 'Open:{0:.2f} Close:{1:.2f}  {2:.2f}% \n ' \
        'Low:{3:.2f} High:{4:.2f}  {5:.2f}%'.format(mkt_open_price[-1], mkt_close_price[0], percent,
                                                  min(mkt_low_price), max(mkt_high_price), hl_percent)
    t4 = ax1.text(0.3, 0.9, s, transform=ax1.transAxes)


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


def generate_graphs():
    while True:
        media_ids = []
        tweet = ''
        for interval in ['day', 'week', 'month', 'year']:
            text = output_graph(interval)
            if not text:
                continue
            tweet += output_graph(interval)
            if args.tweeting:
                photo = open('{0}.png'.format(interval), 'rb')
                try:
                    response = twitter.upload_media(media=photo)
                except TwythonError as err:
                    print('{0}'.format(err))
                    return True
                media_ids += [response['media_id']]
        if args.tweeting:
            try:
                for status in twitter.get_user_timeline(screen_name=SCREEN_NAME):
                    twitter.destroy_status(id=status['id_str'])
                twitter.update_status(status=tweet, media_ids=media_ids)
            except TwythonError as err:
                print('{0}'.format(err))
                print(len(tweet))
            time.sleep(60*10)
        else:
            return True


if __name__ == '__main__':
    if args.tweeting:
        print('tweeting')
        while True:
            now = datetime.now()
            minutes = int(now.strftime('%-M')) + 10
            if minutes % 10 == 0:
                generate_graphs()
            else:
                time.sleep(1)
    else:
        generate_graphs()
