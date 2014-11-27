import base58
import re
import Crypto.Hash.SHA256 as SHA256
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
COPYRIGHT = "Ybcoin"
COPYRIGHT_URL = "mailto:ifind@live.cn"

DONATIONS_BTC = ''
DONATIONS_YBC = 'YTU8JJidCcHtJpYMGPK2eL6zGBVKwd2Jit'

DEFAULT_CONTENT_TYPE = "text/html; charset=utf-8"
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

DEFAULT_LOG_FORMAT = "%(message)s"

LOG10COIN = 6
COIN = 10 ** LOG10COIN

def double_sha256(s):
    return SHA256.new(SHA256.new(s).digest()).digest()

ADDRESS_RE = re.compile('[1-9A-HJ-NP-Za-km-z]{26,}\\Z')

def possible_address(string):
    return ADDRESS_RE.match(string)

def hash_to_address(version, hash):
    vh = version + hash
    return base58.b58encode(vh + double_sha256(vh)[:4])

def decode_check_address(address):
    if possible_address(address):
        version, hash = decode_address(address)
        if hash_to_address(version, hash) == address:
            return version, hash
    return None, None

def decode_address(addr):
    bytes = base58.b58decode(addr, None)
    if len(bytes) < 25:
        bytes = ('\0' * (25 - len(bytes))) + bytes
    return bytes[:-24], bytes[-24:-4]

def short_link(page, link):
    base = base_url
    if base is None:
        env = page['env'].copy()
        env['SCRIPT_NAME'] = posixpath.normpath(
            posixpath.dirname(env['SCRIPT_NAME'] + env['PATH_INFO'])
            + '/' + page['dotdot'])
        env['PATH_INFO'] = link
        full = wsgiref.util.request_uri(env)
    else:
        full = base + link

    return ['<p class="shortlink">短链接: <a href="',
            page['dotdot'], link, '">', full, '</a></p>\n']

def _chain_fields():
    return ["id", "name", "code3", "address_version", "last_block_id"]

def _row_to_chain(store, row):
    if row is None:
        raise NoSuchChainError()
    chain = {}
    fields = _chain_fields()
    for i in range(len(fields)):
        chain[fields[i]] = row[i]
    chain['address_version'] = store.binout(chain['address_version'])
    return chain

def chain_lookup_by_id(store, chain_id):
    return _row_to_chain(store, store.selectrow("""
        SELECT chain_""" + ", chain_".join(_chain_fields()) + """
          FROM chain
         WHERE chain_id = ?""", (chain_id)))

def format_satoshis(satoshis, chain):
    # XXX Should find COIN and LOG10COIN from chain.
    if satoshis is None:
        return ''
    if satoshis < 0:
        return '-' + format_satoshis(-satoshis, chain)
    satoshis = int(satoshis)
    integer = satoshis / COIN
    frac = satoshis % COIN
    return (str(integer) +
            ('.' + (('0' * LOG10COIN) + str(frac))[-LOG10COIN:])
            .rstrip('0').rstrip('.'))

def format_time(nTime):
    import time
    return time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(nTime)))

def main(argv):
    address = "yVFH5gLBEvjeKyH2eniXEqez2eLNCmq4Kb"
    hash_key = "efcca051039f8b791842e16994f9e29b5f8fc445"

    version, binaddr = decode_check_address(address)
    print version
    body = []
    if binaddr is None:
        body += ['<p>Not a valid address.</p>']
        return

    conf = {
        "port":                     None,
        "host":                     None,
        "no_serve":                 None,
        "debug":                    None,
        "static_path":              None,
        "document_root":            None,
        "auto_agpl":                None,
        "download_name":            None,
        "watch_pid":                None,
        "base_url":                 None,
        "logging":                  None,
        "address_history_rows_max": None,
        "shortlink_type":           None,

        "template":     DEFAULT_TEMPLATE,
        "template_vars": {
            "ABE_URL": ABE_URL,
            "APPNAME": ABE_APPNAME,
            "VERSION": ABE_VERSION,
            "COPYRIGHT": COPYRIGHT,
            "COPYRIGHT_YEARS": COPYRIGHT_YEARS,
            "COPYRIGHT_URL": COPYRIGHT_URL,
            "DONATIONS_BTC": DONATIONS_BTC,
            "DONATIONS_YBC": DONATIONS_YBC,
            "CONTENT_TYPE": DEFAULT_CONTENT_TYPE,
            },
        }
    conf.update(DataStore.CONFIG_DEFAULTS)

    #解析参数
    args, argv = readconf.parse_argv(argv, conf)

    store = DataStore.new(args)
    dbhash = store.binin(binaddr)

    print dbhash
    print hash_to_address('N', store.binout(hash_key))
    return

    chains = {}
    balance = {}
    received = {}
    sent = {}
    count = [0, 0]
    chain_ids = []
    def adj_balance(txpoint):
        chain_id = txpoint['chain_id']
        value = txpoint['value']
        if chain_id not in balance:
            chain_ids.append(chain_id)
            chains[chain_id] = chain_lookup_by_id(store, chain_id)
            balance[chain_id] = 0
            received[chain_id] = 0
            sent[chain_id] = 0
        balance[chain_id] += value
        if value > 0:
            received[chain_id] += value
        else:
            sent[chain_id] -= value
        count[txpoint['is_in']] += 1

    txpoints = []
    max_rows = 10
    in_rows = store.selectall("""
        SELECT
            b.block_nTime,
            cc.chain_id,
            b.block_id,
            1,
            b.block_hash,
            tx.tx_hash,
            txin.txin_pos,
            -prevout.txout_value
          FROM chain_candidate cc
          JOIN block b ON (b.block_id = cc.block_id)
          JOIN block_tx ON (block_tx.block_id = b.block_id)
          JOIN tx ON (tx.tx_id = block_tx.tx_id)
          JOIN txin ON (txin.tx_id = tx.tx_id)
          JOIN txout prevout ON (txin.txout_id = prevout.txout_id)
          JOIN pubkey ON (pubkey.pubkey_id = prevout.pubkey_id)
         WHERE pubkey.pubkey_hash = ?
        """ + ("" if max_rows < 0 else """
         LIMIT ?"""),
                  (dbhash,)
                  if max_rows < 0 else
                  (dbhash, max_rows + 1))

    print in_rows
    too_many = False
    if max_rows >= 0 and len(in_rows) > max_rows:
        too_many = True

    if not too_many:
        out_rows = store.selectall("""
            SELECT
                b.block_nTime,
                cc.chain_id,
                b.block_id,
                0,
                b.block_hash,
                tx.tx_hash,
                txout.txout_pos,
                txout.txout_value
              FROM chain_candidate cc
              JOIN block b ON (b.block_id = cc.block_id)
              JOIN block_tx ON (block_tx.block_id = b.block_id)
              JOIN tx ON (tx.tx_id = block_tx.tx_id)
              JOIN txout ON (txout.tx_id = tx.tx_id)
              JOIN pubkey ON (pubkey.pubkey_id = txout.pubkey_id)
             WHERE pubkey.pubkey_hash = ?
               AND cc.in_longest = 1""" + ("" if max_rows < 0 else """
             LIMIT ?"""),
                      (dbhash, max_rows + 1)
                      if max_rows >= 0 else
                      (dbhash,))
        if max_rows >= 0 and len(out_rows) > max_rows:
            too_many = True
        print out_rows
    if too_many:
        body += ["<p>I'm sorry, this address has too many records"
                 " to display.</p>"]
        return

    rows = []
    rows += in_rows
    rows += out_rows
    rows.sort()
    for row in rows:
        nTime, chain_id, height, is_in, blk_hash, tx_hash, pos, value = row
        txpoint = {
                "nTime":    int(nTime),
                "chain_id": int(chain_id),
                "height":   int(height),
                "is_in":    int(is_in),
                "blk_hash": store.hashout_hex(blk_hash),
                "tx_hash":  store.hashout_hex(tx_hash),
                "pos":      int(pos),
                "value":    int(value),
                }
        adj_balance(txpoint)
        txpoints.append(txpoint)

    if (not chain_ids):
        body += ['<p>Address not seen on the network.</p>']
        return

    def format_amounts(amounts, link):
        ret = []
        for chain_id in chain_ids:
            chain = chains[chain_id]
            if chain_id != chain_ids[0]:
                ret += [', ']
            ret += [format_satoshis(amounts[chain_id], chain),
                    ' ', escape(chain['code3'])]
            if link:
                other = util.hash_to_address(
                    chain['address_version'], binaddr)
                if other != address:
                    ret[-1] = ['<a href="', page['dotdot'],
                               'address/', other,
                               '">', ret[-1], '</a>']
        return ret

    """
    if shortlink_type == "firstbits":
        link = store.get_firstbits(
            address_version=version, db_pubkey_hash=dbhash,
            chain_id = (page['chain'] and page['chain']['id']))
        if link:
            link = link.replace('l', 'L')
        else:
            link = address
    else:
        """
    #link = address[0 : shortlink_type]
    #body += short_link(page, 'a/' + link)

    body += ['<p>余额: '] + format_amounts(balance, True)

    for chain_id in chain_ids:
        balance[chain_id] = 0  # Reset for history traversal.

    body += ['<br />\n',
             '交易: ', count[0], '<br />\n',
             '收到: ', format_amounts(received, False), '<br />\n',
             '交易输出: ', count[1], '<br />\n',
             '发出: ', format_amounts(sent, False), '<br />\n']

    body += ['</p>\n'
             '<h3>交易</h3>\n'
             '<table>\n<tr><th>交易</th><th>区块</th>'
             '<th>大约生成时间</th><th>数量</th><th>余额</th>'
             '<th>货币</th></tr>\n']

    for elt in txpoints:
        chain = chains[elt['chain_id']]
        balance[elt['chain_id']] += elt['value']
        body += ['<tr><td><a href="../tx/', elt['tx_hash'],
                 '#', 'i' if elt['is_in'] else 'o', elt['pos'],
                 '">', elt['tx_hash'][:10], '...</a>',
                 '</td><td><a href="../block/', elt['blk_hash'],
                 '">', elt['height'], '</a></td><td>',
                 format_time(elt['nTime']), '</td><td>']
        if elt['value'] < 0:
            body += ['(', format_satoshis(-elt['value'], chain), ')']
        else:
            body += [format_satoshis(elt['value'], chain)]
        body += ['</td><td>',
                 format_satoshis(balance[elt['chain_id']], chain),
                 '</td><td>', escape(chain['code3']),
                 '</td></tr>\n']
    body += ['</table>\n']
    print body

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
