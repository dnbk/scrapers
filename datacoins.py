#!/usr/bin/env python

import sys
import cymysql
import requests
from csv import reader, Dialect
from uuid import uuid4
from os import path
from tabulate import tabulate
from argparse import ArgumentParser
from time import sleep, strftime
from signal import signal, SIGINT
import pdb

###VARIABLES
DBUSER = 'coin'
DBPASSWORD = 'fin'
DBHOST = '127.0.0.1'
DBPORT = 3306
DB = 'coins'
QUOTESTABLE = 'snapshots'
DEBUG = False
SSLVERIFY = False
###


def signal_handler(signal, frame):
    print '\nExiting...'
    exit(1)

def parseargs():
    parser = ArgumentParser()
    parser.add_argument('--flush', action = 'store_true', help = 'Reset %s table' % QUOTESTABLE)
    parser.add_argument('--exchange-remove', help = 'Removes exchange')
    parser.add_argument('--exchange-add', help = 'Adds exchange')
    parser.add_argument('--from-file', type = file, help = 'CSV file with list of currencies')
    parser.add_argument('--data', action = 'store_true', help = 'Pulls data from exchanges')
    parser.add_argument('--list-map', action = 'store_true', help = 'Exchange-symbol map')
    parser.add_argument('--list-symbols', action = 'store_true', help = 'List of symbols')
    parser.add_argument('--list-exchanges', action = 'store_true', help = 'List of exchanges')
    parser.add_argument('-s', '--sleep', type = int, help = 'Sleep for N seconds between polls')
    parser.add_argument('-v', '--verbose', action = 'store_true', help = 'verbose mode')
    parser.add_argument('-t', '--trace', action = 'store_true', help = 'Trace mode')
    if len(sys.argv) == 1:
    	parser.print_help()
    	sys.exit(1)
    return vars(parser.parse_args())

class dbConnect():
    def __init__(self, host, user, passwd, db, port):
        try:
            conn = cymysql.connect(host, user, passwd, db, port, charset = 'utf8')
            self.cursor = conn.cursor()
        except cymysql.err.OperationalError:
            print "Error connecting to database"
            sys.exit(1)

    def __del__(self):
    	try:
        	self.cursor.close()
        except AttributeError:
        	pass

    def runsql(self, sql):
    	if DEBUG: print "Executing SQL: %s" % sql
    	self.cursor.execute(sql)
        return self.cursor.fetchall()

class dbManager(dbConnect):
	def createRTable(self, tablename):
		"""Create real time table for quotes"""
		self.runsql("CREATE TABLE %s (id bigint not null auto_increment, exchange int not null, \
		    trading_pair int not null, time time not null, last double, volume double, open double, \
		    high double, low double, bid double, ask double, primary key (id), \
		    foreign key (exchange) references exchanges(id) on delete restrict on update cascade, \
		    foreign key (trading_pair) references trading_pairs(id) on delete restrict on update \
		    cascade); COMMIT;" % tablename)

	def dropRTable(self, tablename):
		try:
			self.runsql("DROP TABLE %s; COMMIT;" % tablename)
		except cymysql.err.InternalError:
			pass

	def exchangeId(self, exchange):
		return self.runsql("SELECT id FROM exchanges WHERE name = '%s';" % exchange)[0][0]

	def traidingPairsId(self, trading_pair):
		try:
			res = self.runsql("SELECT id FROM trading_pairs WHERE currency_a = \
				(SELECT id FROM currencies WHERE symbol = '%s') AND currency_b = \
				(SELECT id FROM currencies WHERE symbol = '%s');" % trading_pair)[0][0]
		except IndexError, e:
			print 'Error: No such trading pair %s/%s in "trading_pairs" table' % trading_pair
			sys.exit(1)
		return res


class Provider_cryptocoincharts(object):
	""" cryptocoincharts """
	def __init__(self):
		self.url = 'http://www.cryptocoincharts.info/v2/api/tradingPair/%s'
		self.exchange = 'cryptocoincharts'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url % '_'.join(trading_pair)).json()
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		try:
			exchange_id = dbm.exchangeId(self.exchange)
		except IndexError:
			raise 'Unknown provider'
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(price)s, %(volume_first)s); COMMIT;" % values)

class Provider_bitfinex(object):
	"""bitfinex"""
	def __init__(self):
		self.url = 'https://api.bitfinex.com/v1/ticker/%s'
		self.exchange = 'bitfinex'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url % ''.join(trading_pair), verify = SSLVERIFY).json()
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last_price)s, %(bid)s, %(ask)s); COMMIT;" % values)

class Provider_bitstamp(object):
	"""bitstamp"""
	def __init__(self):
		self.url = 'https://www.bitstamp.net/api/ticker'
		self.exchange = 'bitstamp'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url, verify = SSLVERIFY).json()
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(volume)s, %(high)s, %(low)s, %(bid)s, %(ask)s); COMMIT;" % values)


class Provider_bitxsa(object):
	"""bitx South Africa"""
	def __init__(self):
		self.url = 'https://bitx.co.za/api/1/BTCZAR/ticker'
		self.exchange = 'bitx-SA'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url, verify = SSLVERIFY).json()
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last_trade)s, %(rolling_24_hour_volume)s, %(bid)s, %(ask)s); COMMIT;" % values)


class Provider_bter(object):
	"""bter"""
	def __init__(self):
		self.url = 'https://bter.com/api/1/ticker/%s'
		self.exchange = 'bter'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url % '_'.join(trading_pair), verify = SSLVERIFY).json()
		if not values: return
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		#fix for changing vol_
		values.update({'vol': values["vol_%s" % trading_pair[1]]})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(vol)s, %(high)s, %(low)s, %(buy)s, %(sell)s); COMMIT;" % values)


class Provider_coinse(object):
	"""coins-e"""
	def __init__(self):
		self.url = 'https://www.coins-e.com/api/v2/market/%s/depth/'
		self.exchange = 'coins-e'

	def addQuotes(self, trading_pair, verbose = None):
		if verbose: print self.exchange
		values = requests.get(self.url % '_'.join(trading_pair), verify = SSLVERIFY).json()
		if DEBUG: print self.exchange, values
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(ltp)s, %(ltq)s, %(bid)s, %(ask)s); COMMIT;" % values)


class Provider_cryptotrade(object):
	"""crypto-trade"""
	def __init__(self):
		self.url = 'https://crypto-trade.com/api/1/ticker/%s'
		self.exchange = 'crypto-trade'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url % '_'.join(trading_pair), verify = SSLVERIFY).json()
		if not values['status'] == 'success': return
		values = values['data']
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		values.update({'vol': values["vol_%s" % trading_pair[1]]})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(vol)s, %(high)s, %(low)s, %(max_bid)s, %(min_ask)s); COMMIT;" % values)


class Provider_cryptsy(object):
	"""cryptsy"""
	def __init__(self):
		self.url_markets = 'http://pubapi.cryptsy.com/api.php?method=marketdatav2'
		self.exchange = 'cryptsy'

	def addQuotes(self, pairs, verbose = None):
		res = requests.get(self.url_markets, verify = SSLVERIFY)
		if res.status_code != 200:
			print '%s HTTP error on %s' % (res.status_code, self.url_markets)
			return
		res = res.json()
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		del dbm
		for pair in pairs:
			for market, data in res['return']['markets'].iteritems():
				if pair[0].upper() in data['primarycode'] and pair[1].upper() in data['secondarycode']:
					dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)		
					trading_pair_id = dbm.traidingPairsId(pair)
					values = {'exchange': exchange_id, 'trading_pair': trading_pair_id, 'table': QUOTESTABLE, \
						'time': strftime("%H:%M:%S"), 'volume': data['volume'], 'last': data['lasttradeprice']}
					dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume) VALUES \
						(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(volume)s); COMMIT;" % values)
					del dbm


class Provider_emebtc(object):
	"""emebtc"""
	def __init__(self):
		self.url = 'https://emebtc.com/api/1/ticker/%s'
		self.exchange = 'emebtc'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.get(self.url % '_'.join(trading_pair), verify = SSLVERIFY).json()
		if not values['result'] == 'true': return
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		values.update({'vol': values["vol_%s" % trading_pair[1]]})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(vol_ltc)s, %(high)s, %(low)s, %(buy)s, %(sell)s); COMMIT;" % values)


class Provider_litetree(object):
	"""litetree"""
	def __init__(self):
		self.url = 'https://www.litetree.com/api/1.1/ticker'
		self.exchange = 'litetree'

	def addQuotes(self, trading_pair, verbose = None):
		postdata = {'pair': '/'.join(trading_pair)}
		values = requests.post(self.url, data = postdata, verify = SSLVERIFY).json()
		values = values['data']
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if not values['bid']: values.update({'bid': 'NULL'})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(volume)s, %(high)s, %(low)s, %(bid)s, %(ask)s); COMMIT;" % values)


class Provider_therocktrading(object):
	"""therocktrading"""
	def __init__(self):
		self.url = 'https://www.therocktrading.com/api/ticker/%s'
		self.exchange = 'therocktrading'

	def addQuotes(self, trading_pair, verbose = None):
		values = requests.post(self.url % ''.join(trading_pair), verify = SSLVERIFY).json()
		values = values['result'][0]
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(self.exchange)
		trading_pair_id = dbm.traidingPairsId(trading_pair)
		values.update({'exchange': exchange_id, 'trading_pair': trading_pair_id})
		values.update({'table': QUOTESTABLE, 'time': strftime("%H:%M:%S")})
		if DEBUG: print values
		dbm.runsql("INSERT INTO %(table)s (exchange, trading_pair, time, last, volume, high, low, bid, ask) VALUES \
			(%(exchange)s, %(trading_pair)s, '%(time)s', %(last)s, %(volume)s, %(high)s, %(low)s, %(bid)s, %(ask)s); COMMIT;" % values)


def getpairs():
	""" Get map exchange<->trading_pairs """
	exchange_pairs = {}
	dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
	exchanges = dbm.runsql("SELECT name FROM exchanges WHERE deleted = 0;")
	for exchange in exchanges:
		exchange = exchange[0]
		pairs = dbm.runsql("select currency_a, currency_b from trading_pairs where id in \
			(select trading_pair from exchange_pairs_map where exchange = (select id from exchanges \
			where name = '%s' and deleted = 0) and deleted = 0) and deleted = 0;" % exchange)
		exchange_pairs[exchange] = []
		for pair in pairs:
			currency_a = dbm.runsql("SELECT symbol FROM currencies WHERE id = %s AND deleted = 0;" % (pair[0]))
			currency_b = dbm.runsql("SELECT symbol FROM currencies WHERE id = %s AND deleted = 0;" % (pair[1]))
			try:
				exchange_pairs[exchange].append((currency_a[0][0], currency_b[0][0]))
			except IndexError:
				pass
	return exchange_pairs


def addpairs(currency_a, currency_b):
	dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
	try:
		dbm.runsql('INSERT INTO currencies (uuid, updated, deleted, symbol, name) VALUES ("%s", "%s", 0, "%s", "%s"); COMMIT;' % \
			(str(uuid4()), strftime("%Y-%m-%d %H:%M:%S"), currency_a, currency_a))
	except cymysql.err.IntegrityError, e:
		if params['verbose']: print 'Symbol %s is already here' % currency_a
	try:
		dbm.runsql('INSERT INTO currencies (uuid, updated, deleted, symbol, name) VALUES ("%s", "%s", 0, "%s", "%s"); COMMIT;' % \
			(str(uuid4()), strftime("%Y-%m-%d %H:%M:%S"), currency_b, currency_b))
	except cymysql.err.IntegrityError, e:
		if params['verbose']: print 'Symbol %s is already here' % currency_b		
	try:
		dbm.runsql('INSERT INTO trading_pairs (updated, currency_a, currency_b) VALUES ("%s", \
			(SELECT id FROM currencies WHERE name = "%s"), \
			(SELECT id FROM currencies WHERE name = "%s")); COMMIT;' % (strftime("%Y-%m-%d %H:%M:%S"), currency_a, currency_b))
	except cymysql.err.IntegrityError, e:
		if params['verbose']: print 'Trading pair %s/%s is already here' % (currency_a, currency_b)
	del dbm
	dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
	return dbm.traidingPairsId((currency_a, currency_b))


def main():
	if params['flush']:
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		dbm.dropRTable(QUOTESTABLE)
		dbm.createRTable(QUOTESTABLE)
		print 'Flushed %s table.' % QUOTESTABLE
		return
	if params['list_map']:
		exchange_pairs = getpairs()
		table = []
		for key, values in exchange_pairs.iteritems():
			for pair in values:
				table.append([key, pair[0], pair[1]])
		if len(table) == 0:
			print 'No map found'
			return
		print
		print tabulate(table, headers = ['Exchange', 'currency_a', 'currency_b'])
	if params['list_symbols']:
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		res = dbm.runsql('SELECT symbol, name, description FROM currencies WHERE deleted = 0;')
		if len(res) == 0:
			print 'No symbol found'
			return
		print
		print tabulate(res, headers = ['Symbol', 'Name', 'Description'])
	if params['list_exchanges']:
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		res = dbm.runsql('SELECT name, homepage FROM exchanges WHERE deleted = 0;')
		if len(res) == 0:
			print 'No exchange found'
			return
		print
		print tabulate(res, headers = ['Name', 'Homepage'])
	if params['exchange_remove']:
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		try:
			exchange_id = dbm.exchangeId(params['exchange_remove'])
		except IndexError:
			print 'No such %s provider' % params['exchange_remove']
			return
		dbm.runsql('UPDATE exchange_pairs_map SET deleted = 1 WHERE exchange = %s; COMMIT;' % exchange_id)
		dbm.runsql('UPDATE exchanges SET deleted = 1 WHERE name = "%s"; COMMIT;' % params['exchange_remove'])
		del dbm
		# remove orphan trading pairs
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)	
		trading_pairs = dbm.runsql('SELECT id FROM trading_pairs WHERE id NOT IN \
			(SELECT trading_pair FROM exchange_pairs_map WHERE deleted = 0);')
		for trading_pair_id in trading_pairs:
			dbm.runsql('UPDATE trading_pairs SET deleted = 1 WHERE id = %s' % trading_pair_id)
		print "Deleted " + params['exchange_remove']
		return
	if params['exchange_add']:
		exchange, url = tuple(params['exchange_add'].split(','))
		print 'Adding exchange %s with homepage %s' % (exchange, url)
		data = reader(params['from_file'], skipinitialspace = True)
		table = []
		for row in data: table.append(row)
		if params['verbose']:
			print
			print tabulate(table, ['currency_a', 'currency_b'])
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		try:
			dbm.runsql('INSERT INTO exchanges (uuid, updated, deleted, name, homepage) VALUES ("%s", "%s", 0, "%s", "%s"); COMMIT;' % \
				(str(uuid4()), strftime("%Y-%m-%d %H:%M:%S"), exchange, url))
			del dbm
		except cymysql.err.IntegrityError:
			dbm.runsql('UPDATE exchanges SET updated = "%s", deleted = 0, homepage = "%s" WHERE name = "%s"; COMMIT;' % \
				(strftime("%Y-%m-%d %H:%M:%S"), url, exchange))
			del dbm
		dbm = dbManager(DBHOST, DBUSER, DBPASSWORD, DB, DBPORT)
		exchange_id = dbm.exchangeId(exchange)
		for pair in table:
			trading_pair_id = addpairs(pair[0], pair[1])
			if DEBUG: print 'Traiding pair: %s' % trading_pair_id
			try:
				dbm.runsql('INSERT INTO exchange_pairs_map (updated, trading_pair, exchange) VALUES ("%s", %s, %s);' % \
					(strftime("%Y-%m-%d %H:%M:%S"), trading_pair_id, exchange_id))
			except cymysql.err.IntegrityError:
				dbm.runsql('UPDATE exchange_pairs_map SET updated = "%s" WHERE exchange = %s AND trading_pair = %s;' % \
					(strftime("%Y-%m-%d %H:%M:%S"), exchange_id, trading_pair_id))				
		return
	if params['data']:
		exchange_pairs = getpairs()
		while True:
			for exchange in exchange_pairs:
				if exchange == 'cryptocoincharts':
					provider = Provider_cryptocoincharts()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'bitfinex':
					provider = Provider_bitfinex()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'bitstamp':
					provider = Provider_bitstamp()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'bitx-SA':
					provider = Provider_bitxsa()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'bter':
					provider = Provider_bter()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'coins-e':
					provider = Provider_coinse()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'crypto-trade':
					provider = Provider_cryptotrade()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'cryptsy':
					provider = Provider_cryptsy()
					provider.addQuotes(exchange_pairs[exchange], params['verbose'])
				elif exchange == 'emebtc':
					provider = Provider_emebtc()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'litetree':
					provider = Provider_litetree()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				elif exchange == 'therocktrading':
					provider = Provider_therocktrading()
					for pair in exchange_pairs[exchange]:
						provider.addQuotes(pair, params['verbose'])
				else:
					print 'Error: %s - no such provider defined' % exchange
					sys.exit(1)
			if params['sleep']:
				sleepTime = (params['sleep'] < 30) and 30 or params['sleep']
				sleep(sleepTime)
			else:
				return



if __name__ == '__main__':
	params = parseargs()
	signal(SIGINT, signal_handler)
	if params['trace']: pdb.set_trace()
	main()
