import os
from atexit import register as ae_register
from datetime import timedelta
from datetime import datetime as dt

class EasyLogging:
	''' Logging to console and optionally to a disk.
		Attributes:
			level - logging level. Default is 10 ('INFO').
			If level == 0 then show debug messages.
			If level == 20 then show only error messages.
			Default levels:
				'DEBUG' : 0
				'INFO' : 10
				'ERROR' : 20

			time_format:str='%Y.%m.%d %H:%M:%S'

			file_name_format:str='%Y-%m-%d.log'

			directory:str - write log files to this folder.
			If not specified - no logging to a file.

			levels:dict - provide your own levels.
			Format: {'level name 1': level_num1
				, 'level name 2': level_num2}

			add_levels - just add this level(s) to the default
			levels dictionary. Format:
				[('my_level_1', 15), ('my_level_2', 30)]

			line_max_len:int - if specified cut the message
			to that length (log datestamp not included).

			sep:str - separator between columns.
	'''
	def __init__(
		s
		, level:int=10
		, directory:str=None
		, file_name_format:str='%Y-%m-%d.log'
		, time_format:str='%Y.%m.%d %H:%M:%S'
		, add_levels:list=None
		, levels:dict={
			'DEBUG' : 0
			, 'INFO' : 10
			, 'ERROR' : 20
		}
		, line_max_len:int=None
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
				, lambda s, *strings, l=key: s._log(*strings, lvl=l)
			)
			setattr(EasyLogging, key.upper(), value)
		s.lvl_pad = max(*map(len, levels))
		s.sep = sep
		s.line_max_len = line_max_len
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
		ae_register(s._cleanup)

	def _log(s, *strings, lvl:str='DEBUG'):
		'Log to console and optionally to disk'
		if s.levels.get(lvl, s.level) < s.level: return
		msg = s.sep.join(map(str, strings))
		if s.line_max_len: msg = msg[:s.line_max_len]
		t = dt.now().strftime(s.time_format)
		msg = f'{t}{s.sep}{lvl:{s.lvl_pad}}{s.sep}{msg}'
		print(msg)
		if not s.filed: return
		s._write_to_file(msg)
		
	def _cleanup(s):
		if not s.filed: return
		s._log('cleanup', lvl='DEBUG')
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
			s._log(lvl=name.upper(), *args, **kwargs)
		return method

if __name__ == '__main__':
	log = EasyLogging(
		line_max_len=20
	)
	log.debug('This msg will be omitted with default logging level')
	log.info('Info message')
	log.info('Some messages may be too long')
	log.error('Error message')
	log.bye('Goodbye!')
