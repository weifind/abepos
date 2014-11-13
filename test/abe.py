import sys
import os
import optparse
import re
from cgi import escape
import posixpath
import wsgiref.util
import time
import logging
import json

import version
import DataStore
import readconf

import deserialize
import util
import base58

__version__ = version.__version__

ABE_APPNAME = "Ybcoin"
ABE_VERSION = __version__
ABE_URL = 'https://github.com/weifind/ybcoin-abe'

COPYRIGHT_YEARS = '2014'
COPYRIGHT = 'Ybcoin'
COPYRIGHT_URL = 'mail:ifind@live.cn'

DONATIONS_BTC = ''
DONATIONS_YBC = ''

DEFAULT_CONTENT_TYPE = 'text/html; charset=utf-8'
DEFAULT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" type="text/css"
     href="%(dotdot)s%(STATIC_PATH)sabe.css" />
    <link rel="shortcut icon" href="%(dotdot)s%(STATIC_PATH)sfavicon.ico" />
    <title>%(title)s</title>
</head>
<body>
    <h1><a href="%(dotdot)schains"><img
     src="%(dotdot)s%(STATIC_PATH)slogo32.png" alt="Abe logo" /></a> %(h1)s
    </h1>
    %(body)s
    <p><a href="%(dotdot)sq">API</a> 机读格式</p>
    <p style="font-size: smaller">
        <span style="font-style: italic">
            由 <a href="%(ABE_URL)s">Ybcoin-abe</a> 提供技术支持
        </span>
        %(download)s
        , 需要您的捐助
        <!-- <a href="%(dotdot)saddress/%(DONATIONS_BTC)s">BTC</a> -->
        <a href="%(dotdot)saddress/%(DONATIONS_YBC)s">YBC</a>
    </p>
</body>
</html>
"""
DEFAULT_LOG_FORMAT = "%(MESSAGE)s"

LOG10COIN = 6
COIN = 10 ** LOG10COIN

ADDR_PREFIX_RE = re.compile('[1-9A-HJ-NP-Za-km-z]{6,}\\Z')
HEIGHT_RE = re.compile('(?:0|[1-9][0-9]*)\\Z')
HASH_PREFIX_RE = re.compile('[0-9a-fA-F]{0,64}\\Z')
HASH_PREFIX_MIN = 6

NETHASH_HEADER = """\
blockNumber:          height of last block in interval + 1
time:                 block time in seconds since 0h00 1 Jan 1970 UTC
target:               decimal target at blockNumber
avgTargetSinceLast:   harmonic mean of target over interval
difficulty:           difficulty at blockNumber
hashesToWin:          expected number of hashes needed to solve a block at this difficulty
avgIntervalSinceLast: interval seconds divided by blocks
netHashPerSecond:     estimated network hash rate over interval

Statistical values are approximate.

/chain/CHAIN/q/nethash[/INTERVAL[/START[/STOP]]]
Default INTERVAL=144, START=0, STOP=infinity.
Negative values back from the last block.

blockNumber,time,target,avgTargetSinceLast,difficulty,hashesToWin,avgIntervalSinceLast,netHashPerSecond
START DATA
"""

MAX_UNSPENT_ADDRESSES = 200

def make_store(args):
    store = DataStore.new(args)
    store.catch_up()
    return store

class NoSuchChainError(Exception):
    "Thrown when a chain lookup fails"

class PageNotFound(Exception):
    """Thrown when code wants to return 404 Not Found"""

class Redirect(Exception):
    """Thrown when code wants to redirect the request"""

class Streamed(Exception):
    """Thrown when code has written the document to the callable
    returned by start_response."""

class Abe:
    def __init__(abe, store, args):
        abe.store = store
        abe.args = args
        abe.htdocs = args.document_root or find_htdocs()
        abe.static_path = '' if args.static_path is None else args.static_path
        abe.template_vars = args.template_vars.copy()
        abe.template_vars['STATIC_PAHT'] = (
                abe.template_vars.get('STATIC_PATH', abe.static_path))
        abe.template = flatten(args.template)
        abe.debug = args.debug
        abe.log = logging.getLogger(__name__)
        abe.log.info('Abe initialized.')
        abe.home = 'chains'
        if not args.auto_agpl:
            abe.template_vars['download'] = (
                    abe.template_vars.get('download', ''))
        abe.base_uro = args.base_url
        abe.address_hi






























