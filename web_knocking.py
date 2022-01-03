
import configparser
import threading
import time
from http.server import BaseHTTPRequestHandler \
	, ThreadingHTTPServer
import os
from operator import itemgetter
from datetime import datetime as dt, timedelta
from socket import inet_aton
import resources
from rosapi import rosapi_send
from easy_logging import EasyLogging
if os.name == 'nt':
	import ctypes
	import msvcrt

	SetConsoleTitleW = ctypes.windll.kernel32.SetConsoleTitleW

TITLE = 'Web Knocking'
APP_VERSION = 'v2022-01-03'
INI_FILE = 'web_knocking.ini'
DEF_DEVICE_TYPE = 'mikrotik_routeros'
PASS_SEP = '_'

event_counter = 0
sett = None
{
	'1.2.3.4' : {
		'ip' : '1.2.3.4'
		, 'counter' : 0
		, 'status' : 'good'
		, 'reason' : 'white'
		, 'user' : 'John'
	}
}
{
	'John' : {
		'name': 'John'
		, 'passcode' : 's3cReT'
		, 'last_access' : dt.now()
		, 'last_day' : dt(
			2020, 4, 20
		)
		, 'ips': [
			'10.0.1.3'
			, '10.0.8.4'
		]
	}
}
log = None
lang = None

DEF_OPT_GENERAL = [
	('developer', False)
	, ('language', 'en')
	, ('port', 80)
	, ('perm_timeout', '7d 00:00:00')
	, ('temp_timeout', '08:00:00')
	, ('cmd', '/ip firewall address-list add'
			+ ' list={list_name} address={ip}'
			+ ' comment={comment}'
			+ ' timeout={timeout}'
	)
	, ('white_list', 'KNOCKING_WHITE')
	, ('black_list', 'KNOCKING_BLACK')
	, ('black_threshold', 3)
	, ('safe_hosts', ['127.0.0.1'])
	, ('url_prefix', 'http://localhost/')
	, ('log_file', False)
]
DEF_OPT_DEVICE = [
	('device_type', DEF_DEVICE_TYPE)
	, ('port', 8729)
	, ('username', 'admin')
	, ('password', 'admin')
	, ('secure', True)
]

def set_title(add_to_title:str=''):
	if os.name != 'nt': return
	title_str = TITLE
	if add_to_title: title_str += '  |  ' + str(add_to_title)
	SetConsoleTitleW(title_str)

class Settings:
	'''	2020.04.06
		Load settings from .ini file.
		Sections became instance properties:
		[Section1]
		Setting1=123
		[Section2]
		AnotherSetting=lalala
		...
		->
			settings.section1['setting1']
			settings.section2['anothersetting']

		Convert all sections and settings
		to lower case.
		Convert True/yes to bool.
		Convert digits to int
	'''
	def __init__(self, keep_setting_case:bool=False):
		config = configparser.ConfigParser()
		config.optionxform = str
		try:
			with open(INI_FILE, 'tr'
			, encoding='utf-8') as fd:
				config.read_file(fd)
		except FileNotFoundError:
			print(f'{INI_FILE} file not found'
				+ '\nPress any key to exit')
		sections = {
			s.lower() : config._sections[s]
			for s in config._sections
		}
		for section in sections:
			setattr(self, section, {})
			di = sections[section]
			if keep_setting_case:
				settings_names = di.keys()
			else:
				settings_names = [
					k.lower() for k in di]
			for key in settings_names:
				if di[key].lower() in ('true', 'yes'):
					getattr(self, section)[key] = True
				elif di[key].lower() in ('false', 'no'):
					getattr(self, section)[key] = False
				elif di[key].isdigit():
					getattr(self, section)[key] = int(di[key])
				else:
					getattr(self, section)[key] = di[key]

	def __getattr__(self, name):
		try:
			log.debug(f'Settings: unknown key: {name}')
		except:
			print(f'Settings: unknown key: {name}')
		return None

def netmiko_send(cmd, debug:bool=False):
	''' Send command via netmiko '''
	device_params = {
		'device_type': sett.device['device_type']
		, 'host': sett.device['host']
		, 'port': sett.device['port']
		, 'username': sett.device['username']
		, 'password': sett.device['password']
	}
	if debug:
		pass
	try:
		with ConnectHandler(**device_params) as ssh:
			result = ssh.send_command(cmd)
	except Exception as e:
		return False, \
			f'netmiko_send error: {e}'
	return True, result


def send_ip(ip:str, list_name:str=''
, comment:str='', timeout:str=''):
	'''	Send IP to device and return
		status and device answer
	'''
	if is_ros():
		cmd = [
				'/ip/firewall/address-list/add'
				, '=list=' + list_name
				, '=address=' + ip
		]
		if timeout: cmd.append('=timeout=' + timeout)
		if comment: cmd.append('=comment=' + comment)
		result = rosapi_send(
			**sett.rosapi_args
			, cmd = cmd
		)
		if result[0]:
			status, data = ros_answer(result[1])
			log.debug(ip.ljust(15)
				, f'rosapi: {status}, {data}')
	else:
		cmd = sett.device['cmd'].format(
			ip=ip, list_name=list_name
			, comment=comment, timeout=timeout
		)
		result = netmiko_send(cmd)
	return result

def is_ros()->bool:
	'Is it a MikroTik device?'
	return sett.device['device_type'] == \
		DEF_DEVICE_TYPE

def process_ip(ip:str, behavior:str
, reason:str='', user:str=None)->tuple:
	''' Add or not IP to black list on router.
		Return (True, None) on success or
		(False, 'error text') on Exception.
		Three types of behavior:
			'bad' - increment counter of attempts
				and ban when the 'black_threshold'
				is exceeded.
			'good' - reset counter
			'danger' or some string with particular
			
			reason - if none then ban immediately without
				checking 'black_threshold'
	'''
	if not reason: reason = behavior
	if ip in sett.ips and user: sett.ips[ip]['user'] = user
	if behavior != 'good' \
	and ip in sett.general['safe_hosts']:
		log.debug(ip.ljust(15), 'do not ban safe host'
			+ f' ({behavior}: {reason})')
		return True, None
	if behavior != 'good' \
	and ip in sett.ips:
		if sett.ips[ip]['status'] == 'good':
			log.debug(ip.ljust(15), 'do not ban white ip'
				+ f' ({behavior}: {reason})')
			return True, None
	if ip in sett.ips:
		if sett.ips[ip]['status'] == 'white' \
		and behavior == 'danger':
			log.debug(ip.ljust(15)
				, f'white ip: {behavior}: {reason}')
			behavior = 'bad'
	else:
		sett.ips[ip] = {
			'ip': ip
			, 'counter' : 0
			, 'status' : 'grey'
			, 'reason' : 'new'
			, 'user': user
		}
	try:
		if behavior == 'bad':
			cnt = sett.ips[ip]['counter'] + 1
			sett.ips[ip]['counter'] = cnt
			if cnt >= sett.general['black_threshold']:
				behavior = 'danger'
				reason = 'threshold exceed'
			else:
				reason = (
					'{} ({}/{})'.format(
						reason
						, cnt
						, sett.general['black_threshold']
					)
				)
		sett.ips[ip]['reason'] = reason
		if behavior == 'good':
			sett.ips[ip]['counter'] = 0
			sett.ips[ip]['status'] = 'white'
		elif behavior == 'bad':
			log.info(ip.ljust(15), f'bad behavior: {reason}')
		elif behavior == 'danger':
			sett.ips[ip]['status'] = 'black'
			log.info(ip.ljust(15), f'add to black list: {reason}')
			status, data = send_ip(
				ip
				, list_name = sett.general['black_list']
				 , comment = ('web_knocking_'
				 	+ reason.replace(' ', '_')
				 )
			)
			if not status:
				log.error(ip.ljust(15), 'Error on adding to'
					+ f' blacklist: {data}')
		return True, reason
	except Exception as e:
		return False, repr(e)

def ros_answer(ros_data:list)->tuple:
	''' Convert RouterOS API answer
		to (True, data) on success or 
		(False, data) on failed operation.
	'''
	try:
		if ros_data[0][0] == '!done':
			return True, ros_data[0][1].get('=ret'
				, 'unknown reply')
		else:
			return False, ros_data[0][1].get('=message'
				, 'unknown error')
	except Exception as e:
		return False, f'answer error: {e}'

def decision(path:str, ip:str)->list:
	''' Look at path and do corresponding action.
		Returns (True, 'message to show on page')
		on success or (False, 'error text') on
		exception.
	'''
	global sett
	try:
		message = ''
		if path == '/':
			process_ip(ip, behavior='danger', reason='root')
			message = lang.ban
		elif path.startswith('/access'):
			passcode = path.split(PASS_SEP)[1]
			user_name = None
			last_day = None
			for u in sett.users:
				if sett.users[u]['passcode'] == passcode:
					user_name = u
					last_day = sett.users[u]['last_day']
					break
			if user_name:
				if last_day:
					last_day = dt.strptime(
						last_day, '%Y-%m-%d'
					)
					last_day = last_day \
						+ timedelta(days=1)
					if dt.now() \
					< last_day:
						process_ip(ip, behavior='good'
							, reason='valid date access'
							, user=user_name)
						sett.users[user_name]['ips'].append(ip)
						sett.users[user_name]['last_access'] = \
							dt.now()
						log.info(ip.ljust(15)
							, f'valid date access: {user_name}')
						status, data = send_ip(
							ip
							, sett.general['white_list']
							, comment='web_knocking_date_'
								+ passcode
							, timeout=sett.general['temp_timeout']
						)
						if status:
							message = lang.temp_timeout_text \
								.format(user_name)
						else:
							message = lang.access_error \
								.format(user_name)
					else:
						sett.users[user_name]['last_access'] = \
							dt.now()
						log.info(ip.ljust(15)
							, f'date expired: {user_name}')
						process_ip(ip, behavior='bad', reason='date expired'
							, user=user_name)
						message = lang.pass_expired \
							.format(user_name
								, last_day.strftime('%d.%m.%Y'))
				else:
					log.info(ip.ljust(15)
						, f'permanent access: {user_name}')
					process_ip(ip, behavior='good', reason='permanent access'
						, user=user_name)
					sett.users[user_name]['ips'].append(ip)
					sett.users[user_name]['last_access'] = \
						dt.now()
					status, data = send_ip(
						ip
						, sett.general['white_list']
						, comment='web_knocking_permanent_'
							+ passcode
						, timeout=sett.general['perm_timeout']
					)
					if status:
						message = lang.perm_timeout_text \
							.format(user_name)

					else:
						log.debug(ip.ljust(15)
							, f'send_ip error: {data}')
						message = lang.access_error \
							.format(user_name)
			else:
				message = lang.pass_unknown
				process_ip(ip, behavior='bad', reason='unknown user')
		elif path == '/status':
			if ip in sett.general['safe_hosts']:
				try:
					dates = [
						d['last_access']
							for d in sett.users.values()
								if d['last_access']
					]
					if dates:
						last_acc = max(dates)
						for u in sett.users:
							if sett.users[u]['last_access'] == last_acc:
								last_user = u
								last_ip = sett.users[u]['ips'][-1]
								break
						message = '{}\t{}\t{}'.format(
							last_user
							, last_acc.strftime('%Y.%m.%d %H:%M:%S')
							, '.'.join(
								last_ip.split('.')[:2]
							) + '.*.*'
						)
					else:
						message = 'nobody\tnever\nnowhere'
				except Exception as e:
					log.debug(ip.ljust(15)
						, 'status error: ' + repr(e))
					message = 'nobody\tnever\nnowhere'
			else:
				process_ip(ip, behavior='danger', reason='status unsafe')
				message = lang.ban
		elif path == '/reload':
			if ip in sett.general['safe_hosts']:
				status, data = load_settings()
				if status:
					log.info(ip.ljust(15), 'settings reloaded')
					sett = data
					print_users()
					message = 'reloaded'
				else:
					message = 'error'
					log.error('failed to reload settings:', data)
			else:
				process_ip(ip, behavior='danger', reason='reload unsafe')
				message = lang.ban
		else:
			process_ip(ip, behavior='danger', reason='wrong path')
			message = lang.ban
		return True, message			
	except Exception as e:
		process_ip(ip, behavior='bad', reason='decision error')
		log.debug(f'line: {e.__traceback__.tb_lineno}')
		return False, repr(e)

def print_users():
	'Print the dict of users as a table'
	table = [ ['User', 'Last Day', 'Last IP', 'Last Access'] ]
	for user in sett.users.values():
		if last_day := user.get('last_day'):
			if dt.strptime(last_day, '%Y-%m-%d') < dt.now():
				last_day = '*' + last_day
		table.append([
			user['name']
			, last_day
			, user['ips'][-1] if user['ips'] else None
			, user['last_access'].strftime('%Y.%m.%d %H:%M:%S') \
				if user['last_access'] else None
		])
	table_print(table, use_headers=True, sorting=[0])

def print_ips():
	table = [ ['User', 'IP', 'Status', 'Reason'] ]
	for ip in sett.ips.values():
		table.append([
			ip['user']
			, ip['ip']
			, ip['status']
			, ip['reason']
		])
	table_print(table, use_headers=True, sorting=[0, 1])

class KnockHandler(BaseHTTPRequestHandler):
	def handle_one_request(self):
		try:
			super().handle_one_request()
			req_type = str(self.raw_requestline
				, encoding='iso-8859-1').split()[0].upper()
			if req_type != 'GET':
				process_ip(self.address_string()
					, behavior='danger', reason='wrong request method')
		except ConnectionResetError:
			log.debug(self.address_string().ljust(15)
				, 'connection reset')
			process_ip(self.address_string(), behavior='bad'
				, reason='port scan')
		except IndexError:
			try:
				rr = str(self.raw_requestline, encoding='iso-8859-1')
			except Exception as e:
				log.debug(
					self.address_string().ljust(15)
						, 'raw_requestline error: ' + repr(e))
			else:
				log.debug(
					self.address_string().ljust(15)
					, 'raw_requestline: {} (len={})'.format(
						rr, len(rr) )
				)
		except Exception as e:
			log.debug(
				self.address_string().ljust(15)
				, 'h_o_r exception: ' + (repr(e)) \
					+ f'\n\tat line: {e.__traceback__.tb_lineno}'
			)
			process_ip(self.address_string()
				, behavior='danger', reason='h_o_r exception')
				
	def send_error(self, code, message=None
	, explain=None):
		if code > 500:
			self.send_response(200)
			self.send_header('Content-type','text/html; charset=utf-8')
			self.end_headers()
			self.wfile.write(bytes(lang.ban, 'utf-8'))
		else:
			super().send_error(code, message, explain) 

			
	def do_GET(self):
		if 'favicon.' in self.path:
			self.wfile.write(sett.favicon)
			return
		self.send_response(200)
		self.send_header('Content-type','text/html; charset=utf-8')
		self.end_headers()
		status, data = decision(self.path, self.address_string() )
		if status:
			message = data
		else:
			log.debug(
				self.address_string().ljust(15)
				, 'decision error: ' + data
			)
			message = lang.ban
		if self.path == '/status':
			page = message
		else:
			page = sett.html.format(
				message=message
				, timestamp = dt.now() \
					.strftime('%Y.%m.%d %H:%M:%S')
				, ip_address = self.address_string()
				, ip_capt = lang.ip_capt
				, time_capt = lang.time_capt
				, page_title = lang.page_title
			).replace('\n', '').replace('\t', '')
		self.wfile.write(bytes(page, 'utf-8'))

	def log_message(self, msg_format, *args):
		global event_counter
		if args[0].startswith('GET /status') \
		or args[0].startswith('GET /reload') \
		and not sett.general['developer']:
			return
		event_counter += 1
		set_title(event_counter)
		log.http(
			self.address_string().ljust(15)
			, ' '.join(args)
		)

def load_settings()->tuple:
	''' Load settings from .ini file. '''
	global sett
	try:
		new_sett = Settings(keep_setting_case=True)
		for opt in DEF_OPT_GENERAL:
			new_sett.general.setdefault(*opt)
		for opt in DEF_OPT_DEVICE:
			new_sett.device.setdefault(*opt)
			new_sett.ips = {}
		if isinstance(new_sett.general['safe_hosts'], str):
			ip_string = new_sett.general['safe_hosts']
			new_sett.general['safe_hosts'] = []
			for ip in ip_string.split(','):
				new_sett.general['safe_hosts'].append(
					ip.strip()
				)
		users_di = new_sett.users
		new_sett.users = {}
		for user in users_di:
			if ' ' in users_di[user]:
				passcode, last_day = users_di[user].split()
			else:
				passcode = users_di[user]
				last_day = None
			new_sett.users[user] = {
				'name' : user
				, 'passcode' : passcode
				, 'last_access' : None
				, 'last_day' : last_day
				, 'ips' : []
			}
		if os.path.exists('files/index.html'):
			with open('files/index.html'
			, encoding='utf-8') as fd:
				new_sett.html = fd.read()
		else:
			new_sett.html = resources.HTML_DEFAULT
		if os.path.exists('files/favicon.png'):
			with open('files/favicon.png'
			, encoding='rb') as fd:
				new_sett.favicon = fd.read()
		else:
			new_sett.favicon = resources.FAVICON
		if new_sett.device['device_type'] == DEF_DEVICE_TYPE:
			new_sett.rosapi_args = {
				'ip' : new_sett.device['host']
				, 'port' : new_sett.device['port']
				, 'username' : new_sett.device['username']
				, 'password' : new_sett.device['password']
				, 'secure' : new_sett.device['secure']
			}
			if sett:
				new_sett.ips = sett.ips
				for u in sett.users:
					if new_sett.users.get(u):
						new_sett.users[u]['last_access'] = \
							sett.users[u]['last_access']
						new_sett.users[u]['ips'] = sett.users[u]['ips']
		return True, new_sett
	except Exception as e:
		return False, repr(e)

def table_print(table, use_headers=False, row_sep:str=None
, headers_sep:str='-', col_pad:str='  ', row_sep_step:int=0
, sorting=None, sorting_func=None, sorting_rev:bool=False
, repeat_headers:int=None
, empty_str:str='-', consider_empty:list=[None, '']):
	'''	Print list of lists as a table.
		row_sep - string to repeat as a row separator.
		headers_sep - same for header(s).
	'''

	DEF_SEP = '-'

	def print_sep(sep=row_sep):
		nonlocal max_row_len
		if not sep: return
		print( sep * (max_row_len // len(sep) ) )
	
	def print_headers(both=False):
		nonlocal headers, template
		if not headers: return
		if both: print_sep(sep=headers_sep)
		print(template.format(*headers))
		print_sep(sep=headers_sep)

	headers = []
	if not table: return
	if use_headers and not headers_sep: headers_sep = DEF_SEP
	if row_sep_step and not row_sep: row_sep = DEF_SEP
	if row_sep and not headers_sep: headers_sep = row_sep
	if isinstance(table[0], list):
		rows = [l[:] for l in table]
	elif isinstance(table[0], tuple):
		rows = [list(t) for t in table]
	elif isinstance(table[0], dict):
		rows = [list( di.values() ) for di in table]
		if use_headers == True: headers = list( table[0].keys() )
	if isinstance(use_headers, list):
		headers = use_headers
	elif use_headers == True:
		headers = rows.pop(0)
	for row in rows:
		row[:] = [empty_str if i in consider_empty else str(i) for i in row]
	if sorting: sort_key = itemgetter(*sorting)
	if sorting_func:
		if isinstance(sorting_func, (tuple, list)):
			sfunc, item = sorting_func
		else:
			sfunc = sorting_func
			item = 0
		sort_key = lambda l, f=sfunc, i=item: f(l[i])
	if sorting or sorting_func:
		if use_headers:
			rows = [ headers, *sorted(rows, key=sort_key
				, reverse=sorting_rev) ]
		else:
			rows.sort(key=sort_key, reverse=sorting_rev)
	else:
		if headers: rows.insert(0, headers)
	col_sizes = [ max( map(len, col) ) for col in zip(*rows) ]
	max_row_len = sum(col_sizes) + len(col_pad) * (len(col_sizes) - 1)
	template = col_pad.join(
		[ '{{:<{}}}'.format(s) for s in col_sizes ]
	)
	if headers: rows.pop(0)
	print()
	if headers: print_headers(False)
	for row_num, row in enumerate(rows):
		if row_sep_step:
			pr = (row_num > 0)  and (row_num % row_sep_step == 0)
			if pr:
				print_sep()
			if repeat_headers:
				if headers and row_num > 0 \
				and (row_num % repeat_headers == 0):
					print_headers(not pr)
		else:
			if repeat_headers:
				if row_num > 0 and (row_num % repeat_headers == 0):
					print_headers(True)
		print(template.format(*row))
	print()

def main():
	global sett
	global log
	global lang
	if os.name == 'nt':
		set_title()

		def key_wait():
			global sett
			while True:
				if msvcrt.kbhit():
					key = msvcrt.getch()
					log.debug('key:', key)
					if key in b'uU\xa3\x83':
						print_users()
					elif key in b'iI\xe8\x98':
						print_ips()
					elif key in b'sS\xeb\x9b':
						log.info('reload settings')
						status, data = load_settings()
						if status:
							sett = data
							print_users()
						else:
							log.error('failed to reload settings:', data)
				time.sleep(0.001)
		threading.Thread(target=key_wait, daemon=True).start()
	
	status, sett = load_settings()
	if not status:
		print('Error loading settings:', sett)
		exit(1)
	if sett.general['developer']:
		log = EasyLogging(
			level=0, directory='logs'
			, add_levels=('HTTP', 10)
		)
	else:
		d = 'logs' if sett.general['log_file'] else None
		log = EasyLogging(directory=d, add_levels=('HTTP', 10))
	lang = resources.Language(sett.general['language'])
	print('It\'s a wonderful day to ban some robots!')
	print(f'Version: {APP_VERSION}')
	print(lang.homepage)
	print(lang.donate + '\n')
	if sett.general['developer']:
		print('\nDEVELOPER MODE')
	if is_ros():
		status, data = rosapi_send(
			**sett.rosapi_args
			, cmd=[r'/log/info'
				, "=message=knock-knock"]
			, print_debug=sett.general['developer']
		)
		if status:
			log.info(sett.device['host'].ljust(15)
				, f'Access to device: OK')
		else:
			log.error(
				sett.device['host'].ljust(15)
				, f'Access to device error: {data}\n'
					+ 'Check "/ip services"\n'
					+ 'Check firewalls\n'
			)
	print_users()
	try:
		port = sett.general['port'] 
		httpd = ThreadingHTTPServer(
			('0.0.0.0', port)
			, KnockHandler
		)
		log.info(sett.device['host'].ljust(15)
			, f'Start listening on {port} port')
		httpd.serve_forever()
	except KeyboardInterrupt:
		log.info('Terminated by keyboard')
	except Exception as e:
		log.info(f'General error: {e}')

if __name__ == '__main__': main()
