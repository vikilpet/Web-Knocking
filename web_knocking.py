
import configparser
import logging
from http.server import BaseHTTPRequestHandler \
	, ThreadingHTTPServer
import os
import time
from operator import itemgetter
import datetime
from netmiko import ConnectHandler
import resources
from rosapi import rosapi_send

APP_VERSION = 'v2020-04-12'
INI_FILE = 'web_knocking.ini'
DEF_DEVICE_TYPE = 'mikrotik_routeros'


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
		, 'last_access' : datetime.datetime.now()
		, 'last_day' : datetime.datetime(
			2020, 4, 20
		)
		, 'ips': [
			'10.0.1.3'
			, '10.0.8.4'
		]
	}
}
logger = None
lang = None

DEF_OPT_GENERAL = [
	('developer', False)
	, ('language', 'en')
	, ('port', 80)
	, ('perm_timeout', '7d 00:00:00')
	, ('perm_timeout_text'
		, 'access granted for one week')
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
]
DEF_OPT_DEVICE = [
	('device_type', DEF_DEVICE_TYPE)
	, ('port', 8729)
	, ('username', 'admin')
	, ('password', 'admin')
	, ('secure', True)
]

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
			, encoding='utf-8-sig') as fd:
				config.read_file(fd)
		except FileNotFoundError:
			log_error(f'{INI_FILE} file not found'
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
			log_debug(f'Settings: unknown key: {name}')
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
		logging.basicConfig(level=logging.WARNING)
		logger2 = logging.getLogger('netmiko')
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
			log_debug(f'rosapi: {status}, {data}')
	else:
		cmd = sett.device['cmd'].format(
			ip=ip, list_name=list_name
			, comment=comment, timeout=timeout
		)
		result = netmiko_send(cmd)
	return result

def log_debug(msg): logger.debug(msg)
def log_info(msg): logger.info(msg)
def log_error(msg): logger.error(msg)

def is_ros()->bool:
	'Is it MikroTik device?'
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
		log_debug(
			f'do not ban safe host {ip}'
			+ f' ({behavior}: {reason})'
		)
		return True, None
	if behavior != 'good' \
	and ip in sett.ips:
		if sett.ips[ip]['status'] == 'good':
			log_debug(
				f'do not ban white ip {ip}'
				+ f' ({behavior}: {reason})'
			)
			return True, None
	if not ip in sett.ips:
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
			log_debug(f'bad behavior of IP {ip}: {reason}')
		elif behavior == 'danger':
			sett.ips[ip]['status'] = 'black'
			log_info(
				f'add {ip} to black list'
				+ f' for: {reason}')
			status, data = send_ip(
				ip
				, list_name = \
					sett.general['black_list']
				 , comment = ('web_knocking_'
				 	+ reason.replace(' ', '_')
				 )
			)
			if not status:
				log_error(
					'Error on adding to'
					+ f' blacklist IP {ip}: {data}'
				)
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
			message = 'ban'
		elif path.startswith('/access'):
			passcode = path.split('?')[1]
			user_name = None
			last_day = None
			for u in sett.users:
				if sett.users[u]['passcode'] == passcode:
					user_name = u
					last_day = sett.users[u][
						'last_day'
					]
					break
			if user_name:
				if last_day:
					last_day = datetime.datetime.strptime(
						last_day, '%Y-%m-%d'
					)
					last_day = last_day \
						+ datetime.timedelta(days=1)
					if datetime.datetime.now() \
					< last_day:
						process_ip(ip, 'good', 'valid date access')
						sett.users[user_name]['ips'].append(ip)
						sett.users[user_name]['last_access'] = \
							datetime.datetime.now()
						log_info(f'valid date access: {user_name} (IP {ip})')
						status, data = send_ip(
							ip
							, sett.general['white_list']
							, comment='web_knocking_date_'
								+ passcode
							, timeout=sett.general['temp_timeout']
						)
						if status:
							message =  f'{user_name}, valid date access'
						else:
							message = 'valid date access error'
					else:
						sett.users[user_name]['last_access'] = \
							datetime.datetime.now()
						process_ip(ip, 'bad', 'date expired')
						message = f'{user_name}, access is expired'
				else:
					log_info(f'permanent access: {user_name} (IP {ip})')
					process_ip(ip, 'good', 'permanent access')
					sett.users[user_name]['ips'].append(ip)
					sett.users[user_name]['last_access'] = \
						datetime.datetime.now()
					status, data = send_ip(
						ip
						, sett.general['white_list']
						, comment='web_knocking_permanent_'
							+ passcode
						, timeout=sett.general['perm_timeout']
					)
					if status:
						message = f'{user_name}, access granted'
					else:
						log_debug(f'send ip: {data}')
						message = 'access error'
			else:
				message = f'unknown user "{passcode[:20]}"'
				process_ip(ip, 'bad', 'unknown user')
		elif path == '/status':
			if ip in sett.general['safe_hosts']:
				print_users()
				if sett.ips:
					last_ip = list(sett.ips.keys())[-1]
					last_reason = sett.ips[last_ip]['reason']
					last_ip = '.'.join(last_ip.split('.')[:2]) \
						 + '.*.*'
				else:
					last_ip = '-'
					last_reason = '-'
				message = f'last ip: {last_ip}, status: {last_reason}'
			else:
				process_ip(ip, 'danger', 'status unsafe')
				message = 'ban'
		else:
			process_ip(ip, 'danger', 'wrong path')
			message = 'ban'
		return True, message			
	except Exception as e:
		process_ip(ip, 'bad', 'decision error')
		return False, repr(e)

def print_users():
	print('\nUSER        LAST IP         LAST DAY'
		+ '  LAST ACCESS')
	for u in sett.users:
		if sett.users[u]['ips']:
			last_ip = sett.users[u]['ips'][-1]
		else:
			last_ip = '-'
		last_day = sett.users[u].get('last_day', '')
		if last_day == None: last_day = '-'
		last_access = sett.users[u].get('last_access', None)
		if last_access:
			last_access = last_access.strftime(
				'%Y-%m-%d %H:%M:%S')
		else:
			last_access = '-'
		print(
			f'{u:{12}}{last_ip:{16}}'
			+ f'{last_day:{10}}{last_access}'
		)
	print('\n')

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
				, 'iso-8859-1').split()[0].upper()
			if req_type != 'GET':
				process_ip(s.address_string()
					, 'danger', 'wrong request method')
		except Exception as e:
			log_debug('handle_one_request exception:'
				+ f' {repr(e)[:40]}')
			process_ip(s.address_string()
				, 'danger', 'port scan')
				
	def send_error(s, code, message=None
	, explain=None):
		if code > 500:
			s.send_response(200)
			s.send_header('Content-type','text/html; charset=utf-8')
			s.end_headers()
			s.wfile.write(bytes('ban', 'utf-8'))
		else:
			super().send_error(code, message, explain) 

			
	def do_GET(s):
		if 'favicon.' in s.path:
			log_debug(f'favicon request: {s.path}')
			s.wfile.write(b'<link rel="icon" href="data:,">')
			return
		s.send_response(200)
		s.send_header('Content-type','text/html; charset=utf-8')
		s.end_headers()
		status, data = decision(s.path, s.address_string())
		if status:
			message = data
		else:
			log_error(f'decision error: {data}')
			message = 'Decision error'
		page = sett.html.format(
			message=message
			, timestamp=time.strftime('%Y.%m.%d %H:%M:%S')
			, ip_address=s.address_string()
			, ip_capt=lang.ip_capt
			, time_capt=lang.time_capt
			, page_title=lang.page_title
		).replace('\n', '').replace('\t', '')
		s.wfile.write(bytes(page, 'utf-8'))

	def log_message(s, msg_format, *args):
		if sett.general['developer']:
			log_info(
				'HTTP : '
				+ s.address_string() + ' - '
				+ ' '.join(args)
			)

def main():
	global sett
	global logger
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
		log_level = logging.DEBUG
		log_format = '%(asctime)s : %(levelname)s\t: %(message)s'
	else:
		log_level = logging.INFO
		log_format = '%(asctime)s %(message)s'
	logger = logging.getLogger(__name__)
	logger.setLevel(log_level)
	ch = logging.StreamHandler()
	ch.setLevel(log_level)
	formatter = logging.Formatter(log_format, "%Y.%m.%d %H:%M:%S")
	ch.setFormatter(formatter)
	logger.addHandler(ch)

	if os.path.exists('files/index.html'):
		with open('files/index.html') as fd:
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
			log_info(f'Access to device: OK')
		else:
			log_error(
				f'Access to device error: {data}\n'
				+ 'Check "/ip services"\n'
				+ 'Check firewalls\n'
			)
	if sett.general['developer']:
		print('\nDeveloper mode\n')
	print_users()
	try:
		port = sett.general['port'] 
		httpd = ThreadingHTTPServer(
			('0.0.0.0', port)
			, KnockHandler
		)
		log_info(f'Start listening on {port} port')
		httpd.serve_forever()
	except KeyboardInterrupt:
		log_info('Terminated by keyboard')
	except Exception as e:
		log_info(f'General error: {e}')

if __name__ == '__main__': main()
