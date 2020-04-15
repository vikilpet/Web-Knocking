class Language():
	def __init__(self, language:str='en'):
		if language == 'ru':
			lang_str = dictionary_ru
		else:
			lang_str = dictionary_en
		di = dict(v.split('=') for v in lang_str[:-1].split('\n'))
		self.__dict__.update(di)

dictionary_en='''\
homepage=Homepage: https://github.com/vikilpet/
donate=Donate, if you like it: https://www.paypal.me/vikil
time_capt=Time
ip_capt=Your IP
page_title=Knock-knock
access_error={}<br>there is some error
pass_expired={}<br>your passcode is expired: {}
pass_unknown=Unknown passcode
ban=Ban
perm_timeout_text={}<br>access granted
temp_timeout_text={}<br>access granted for 8 hours
'''

dictionary_ru='''\
homepage=Домашняя страница: https://vikilpet.wordpress.com/
donate=Благодарю за использование
time_capt=Время
ip_capt=Ваш IP
page_title=Тук-тук
access_error={}<br>какая-то ошибка
pass_expired={}<br>ваш код доступа уже истёк: {}
pass_unknown=Неизвестный код доступа
ban=Бан
perm_timeout_text={}<br>доступ открыт
temp_timeout_text={}<br>доступ открыт на 8 часов
'''

HTML_DEFAULT = '''\
<!DOCTYPE html>
<html>
<head>
	<title>{page_title}</title>
	<meta http-equiv=Content-Type content="text/html;charset=UTF-8">
		<style>
			.popup {{
				position: fixed;
				top: 10%;
				left: 50%;
			}}
			.popup .wrapper {{
				max-width: 500px;
				font-size: xx-large;
				text-align: center;
				position: relative;
				left: -50%;
				/*popup-styles*/
				background-color: #eee;
				padding: 20px;
				border-radius: 10px;
			}}
			html {{
				background-color: #ddd;
			}}
			hr {{
				color: #fff;
			}}
			.info {{
				/*text-align: left;*/
				font-family: Verdana;
				line-height: 150%;
				font-size: small;
				color: #999;
			}}
		</style>
	</head>
<body>
	<div class="popup">
		<div class="wrapper">
			{message}<br>
			<hr>
			<p class="info">
				{ip_capt}: {ip_address}<br>
				{time_capt}: {timestamp}<br>
				<a href="https://github.com/vikilpet/">© https://github.com/vikilpet/</a><br>
			</p>
		</div>
	</div>
</body>
</html>
'''