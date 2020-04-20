
import configparser
import atexit
from http.server import BaseHTTPRequestHandler \
	, ThreadingHTTPServer
import os
from datetime import datetime as dt, timedelta
import resources
from rosapi import rosapi_send

APP_VERSION = 'v2020-04-20'
INI_FILE = 'web_knocking.ini'
DEF_DEVICE_TYPE = 'mikrotik_routeros'
PASS_SEP = '_'


sett = None
{
	'1.2.3.4' : {
		'counter' : 0
		, 'status': 'good'
	}
}
{
	'John' : {
		'passcode' : 's3cReT'
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
class EasyLogging:
	''' Logging to console and optionally to a disk.
		Attributes:
			level - log level. Default is 10 ('INFO')
			Default levels:
				'DEBUG' : 0
				'INFO' : 10
				'ERROR' : 20

			time_format:str='%Y.%m.%d %H:%M:%S'

			file_name_format:str='%Y-%m-%d.log'

			directory - write log files to this folder.
			If not specified - no logging to a file.

			levels:dict - provide your own levels.
			Format: {'level name 1': level_num1
				, 'level name 2': level_num2}

			add_levels - just add this level(s) to the default
			levels. Format:
				(('lvl 1', lvl_num1), ('lvl 2', lvl_num2))
			
			sep - separator between columns.
	'''
	def __init__(s
		, level:int=20
		, directory:str=None
		, file_name_format:str='%Y-%m-%d.log'
		, time_format:str='%Y.%m.%d %H:%M:%S'
		, add_levels:list=None
		, levels:dict={
			'DEBUG' : 0
			, 'INFO' : 10
			, 'ERROR' : 20
		}
		, sep:str = ' : '
	):
		s.levels = levels
		if add_levels:
			if type(add_levels[0]) in [list, tuple]:
				for l, n in add_levels:
					s.levels[l] = n
			else:
				s.levels[add_levels[0]] = add_levels[1]
		s.level = level
		s.time_format = time_format
		for key, value in levels.items():
			setattr(
				EasyLogging
				, key.lower()
				, lambda s, *strings, l=key: s._log(*strings, level=l)
			)
			setattr(EasyLogging, key.upper(), value)
		s.lvl_pad = max(*map(len, levels))
		s.sep = sep
		s.filed = None
		if directory:
			if not os.path.exists(directory): os.mkdir(directory)
			s.file_name_format = file_name_format
			s.directory = directory
			s.file_name = dt.now().strftime(
				file_name_format)
			s.filed = open(
				os.path.join(s.directory, s.file_name)
				, 'ta+'
			)
		atexit.register(s._cleanup)

	def _log(s, *strings, level:str='DEBUG'):
		'Log to console and optionally to disk'
		if s.levels.get(level, 0) < s.level: return
		string = s.sep.join(strings)
		t = dt.now().strftime(s.time_format)
		msg = f'{t}{s.sep}{level:{s.lvl_pad}}{s.sep}{string}'
		print(msg)
		if not s.filed: return
		s._write_to_file(msg)
		
	def _cleanup(s):
		if not s.filed: return
		s._log('cleanup', level='DEBUG')
		s.filed.close()
	
	def _write_to_file(s, msg):
		fn = dt.now().strftime(s.file_name_format)
		if fn != s.file_name:
			s.file_name = fn
			s.filed.close()
			s.filed = open(
				os.path.join(s.directory, s.file_name)
				, 'ta+'
			)
		s.filed.write(msg + '\n')
		s.filed.flush()

	def __getattr__(s, name):
		def method(*args, **kwargs):
			s._log(level=name.upper(), *args, **kwargs)
		return method

class Settings:
	'''	2020.04.06 20:48:34
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
	def __init__(s, keep_setting_case:bool=False):
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
			setattr(s, section, {})
			di = sections[section]
			if keep_setting_case:
				settings_names = di.keys()
			else:
				settings_names = [
					k.lower() for k in di]
			for key in settings_names:
				if di[key].lower() in ['true', 'yes']:
					getattr(s, section)[key] = True
				elif di[key].lower() in ['false', 'no']:
					getattr(s, section)[key] = False
				elif di[key].isdigit():
					getattr(s, section)[key] = int(di[key])
				else:
					getattr(s, section)[key] = di[key]

	def __getattr__(s, name):
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
, reason:str='')->tuple:
	''' Add or not IP to black list on router.
		Return (True, None) on success or
		(False, 'error text') on Exception.
		Three types of behavior:
			'bad' - increment counter of attempts
				and ban when the 'black_threshold'
				is exceeded.
			'good' - reset counter
			'danger' or some string with particular
			reason - ban immediately without
				checking 'black_threshold'
	'''

	if not reason: reason = behavior
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
			'counter' : 0
			, 'status' : 'grey'
			, 'reason' : 'new'
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
			log.debug(ip.ljust(15), f'bad behavior: {reason}')
		elif behavior == 'danger':
			sett.ips[ip]['status'] = 'black'
			log.info(ip.ljust(15), f'add to black list: {reason}')
			status, data = send_ip(
				ip
				, list_name = \
					sett.general['black_list']
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
	try:
		message = ''
		if path == '/':
			process_ip(ip, 'danger', 'root')
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
						process_ip(ip, 'good', 'valid date access')
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
						process_ip(ip, 'bad', 'date expired')
						message = lang.pass_expired \
							.format(user_name
								, last_day.strftime('%d.%m.%Y'))
				else:
					log.info(ip.ljust(15)
						, f'permanent access: {user_name}')
					process_ip(ip, 'good', 'permanent access')
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
				print_users()
			else:
				message = lang.pass_unknown
				process_ip(ip, 'bad', 'unknown user')
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
				process_ip(ip, 'danger', 'status unsafe')
				message = lang.ban
		else:
			process_ip(ip, 'danger', 'wrong path')
			message = lang.ban
		return True, message			
	except Exception as e:
		process_ip(ip, 'bad', 'decision error')
		return False, repr(e)

def print_users():
	'Print the dict of users as a table'
	headers = ['USER', 'LAST DAY', 'LAST IP'
		, 'LAST ACCESS']
	rows = [headers]
	for u in sett.users:
		if sett.users[u]['ips']:
			last_ip = sett.users[u]['ips'][-1]
		else:
			last_ip = '-'
		try:
			last_access = sett.users[u] \
				['last_access'].strftime('%Y.%m.%d %H:%M:%S')
		except:
			last_access = '-'
		rows.append([
			u
			, sett.users[u].get('last_day', None)
			, last_ip
			, last_access
		])
	for row in rows:
		row[:] = [i if i else '-' for i in row]
	col_sizes = [
		max( map(len, col)) for col in zip(*rows)
	]
	template = '  '.join(
		[ '{{:<{}}}'.format(s) for s in col_sizes ]
	)
	print('')
	for row in rows: print(template.format(*row))
	print('')

def print_ips():
	print('\nIP               STATUS  REASON')
	for ip in sett.ips:
		status = sett.ips[ip]['status']
		reason = sett.ips[ip]['reason']
		print(f'{ip:{16}}', f'{status:{7}}'
			, reason)
	print('\n')

class KnockHandler(BaseHTTPRequestHandler):
	def handle_one_request(s):
		try:
			super().handle_one_request()
			req_type = str(s.raw_requestline
				, encoding='iso-8859-1').split()[0].upper()
			if req_type != 'GET':
				process_ip(s.address_string()
					, 'danger', 'wrong request method')
		except ConnectionResetError:
			log.debug(s.address_string().ljust(15)
				, 'connection reset')
			process_ip(s.address_string(), 'bad', 'port scan')
		except IndexError:
			try:
				rr = str(s.raw_requestline, encoding='iso-8859-1')
			except Exception as e:
				log.debug(
					s.address_string().ljust(15)
						, 'raw_requestline error: ' + repr(e))
			else:
				log.debug(
					s.address_string().ljust(15)
					, 'raw_requestline: {} (len={})'.format(
						rr, len(rr) )
				)
		except Exception as e:
			log.debug(
				s.address_string().ljust(15)
				, 'h_o_r exception: ' + (repr(e)[:40])
			)
			process_ip(s.address_string()
				, 'danger', 'h_o_r exception')
				
	def send_error(s, code, message=None
	, explain=None):
		if code > 500:
			s.send_response(200)
			s.send_header('Content-type','text/html; charset=utf-8')
			s.end_headers()
			s.wfile.write(bytes(lang.ban, 'utf-8'))
		else:
			super().send_error(code, message, explain) 

			
	def do_GET(s):
		if 'favicon.' in s.path:
			log.debug(s.address_string().ljust(15)
				, f'favicon request: {s.path}')
			s.wfile.write(b'<link rel="icon" href="data:,">')
			return
		s.send_response(200)
		s.send_header('Content-type','text/html; charset=utf-8')
		s.end_headers()
		status, data = decision(s.path, s.address_string() )
		if status:
			message = data
		else:
			log.debug(
				s.address_string().ljust(15)
				, 'decision error: ' + data
			)
			message = lang.ban
		if s.path == '/status':
			page = message
		else:
			page = sett.html.format(
				message=message
				, timestamp = dt.now() \
					.strftime('%Y.%m.%d %H:%M:%S')
				, ip_address = s.address_string()
				, ip_capt = lang.ip_capt
				, time_capt = lang.time_capt
				, page_title = lang.page_title
			).replace('\n', '').replace('\t', '')
		s.wfile.write(bytes(page, 'utf-8'))

	def log_message(s, msg_format, *args):
		if sett.general['developer']:
			log.http(
				s.address_string().ljust(15)
				, ' '.join(args)
			)

def main():
	global sett
	global log
	global lang
	try:
		os.system('title Web Knocking')
	except:
		pass
	sett = Settings(keep_setting_case=True)
	for opt in DEF_OPT_GENERAL:
		sett.general.setdefault(*opt)
	for opt in DEF_OPT_DEVICE:
		sett.device.setdefault(*opt)
	if sett.general['developer']:
		log = EasyLogging(
			level=10, directory='logs'
			, add_levels=('HTTP', 10)
			, sep=' : '
		)
	else:
		d = 'logs' if sett.general['log_file'] else None
		log = EasyLogging(directory=d)
	if os.path.exists('files/index.html'):
		with open('files/index.html'
		, encoding='utf-8') as fd:
			sett.html = fd.read()
	else:
		sett.html = resources.HTML_DEFAULT
	sett.ips = {}
	if isinstance(sett.general['safe_hosts'], str):
		ip_string = sett.general['safe_hosts']
		sett.general['safe_hosts'] = []
		for ip in ip_string.split(','):
			sett.general['safe_hosts'].append(
				ip.strip()
			)
	users_di = sett.users
	sett.users = {}
	for user in users_di:
		if ' ' in users_di[user]:
			passcode, last_day = \
				users_di[user].split()
		else:
			passcode = users_di[user]
			last_day = None
		sett.users[user] = {
			'passcode' : passcode
			, 'last_access' : None
			, 'last_day' : last_day
			, 'ips' : []
		}
	lang = resources.Language(sett.general['language'])
	print('It\'s a wonderful day to ban some robots!')
	print(f'Version: {APP_VERSION}')
	print(lang.homepage)
	print(lang.donate + '\n')
	if is_ros():
		sett.rosapi_args = {
			'ip' : sett.device['host']
			, 'port' : sett.device['port']
			, 'username' : sett.device['username']
			, 'password' : sett.device['password']
			, 'secure' : sett.device['secure']
		}
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
	if sett.general['developer']:
		print('\nDEVELOPER MODE')
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
