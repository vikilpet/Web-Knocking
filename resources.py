class Language():
	def __init__(self, language:str='en'):
		if language == 'ru':
			lang_str = dictionary_ru
		else:
			lang_str = dictionary_en
		di = dict(v.split('=') for v in lang_str[:-1].split('\n'))
		self.__dict__.update(di)

FAVICON = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x08\x03\x00\x00\x00(-\x0fS\x00\x00\x00\x81PLTE\xff\xff\xff\x83\x83\x82\xa7\xa7\xa6~\x7f}qrp\xfd\xfd\xfc\xe1\xe1\xe0\xde\xde\xde\xba\xba\xb9\x95\x95\x94\x88\x89\x87\xf1\xf1\xf1\xeb\xeb\xea\xe6\xe6\xe5\xd1\xd1\xd1\xce\xce\xcd\x92\x92\x91xxw\xf9\xf9\xf9\xf5\xf5\xf4\xee\xee\xed\xe3\xe3\xe3\xca\xca\xc9\xc2\xc2\xc1\xbc\xbc\xbb\xb2\xb2\xb1\xad\xad\xac\x9f\x9f\x9e\x9a\x9a\x99\x97\x97\x97\x8e\x8e\x8c||{zzyijh\xa4\xa4\xa3\xa3\xa3\xa3\xa1\xa1\xa1\x80\x80\x80ddb^^\\UUTRRPAA@n\xda.\xc4\x00\x00\x00\x92IDAT\x18\xd3}\x8fG\x0e\xc30\x0c\x04IIVq\x97{/\xe9\xc9\xff\x1f\x18\xc92\x82\xf8\xe2\x05\x88\xe5\xcc\x81\x00\xe1,\xaa?r\x92\xd6\xc3A\xa4\xf1]\x15n\x8d\x14I|l\xe9\xd8H\x8b\x01NE\xcfb\xc06\xe1\xdcp\xaeC \xd9+\xe0\x0c\\F\x01\xd1\xa7\xac\x9e\xe9\xd08\xb1\x00\x84\xbe^K\x90\xc4\tj\xc6\x17\xa8\xe6\xeb\xb2\xb1\x87V\xc0\xa5\xf6\xe4~d6S\x81x\xd0nu\x02\x83\xad\x98d\x93\x13!\xcdmu\xef\x18\xf6D\x14\xc9M\x13\xef\xef\x8bL\xf0\x1f~\x01c\xeb\x06\x95_\x99Rn\x00\x00\x00\x00IEND\xaeB`\x82'

dictionary_en='''\
homepage=Homepage: https://github.com/vikilpet/
donate=Donate if you like it: https://www.paypal.me/vikil
time_capt=Time
ip_capt=Your IP
page_title=Knock-knock
access_error=You are logged in as «{}»<br>There is some error :(
pass_expired=You are logged in as «{}»<br>Your passcode has expired: {}
pass_unknown=Unknown passcode
ban=Ban
perm_timeout_text=You are logged in as «{}»<br>Access granted
temp_timeout_text=You are logged in as «{}»<br>Access granted for 8 hours
'''

dictionary_ru='''\
homepage=Домашняя страница: https://vikilpet.wordpress.com/
donate=Благодарю за использование
time_capt=Время
ip_capt=Ваш IP
page_title=Тук-тук
access_error=Вы вошли как «{}»<br>Какая-то ошибка включения доступа :(
pass_expired=Вы вошли как «{}»<br>Ваш код доступа уже истёк: {}
pass_unknown=Неизвестный код доступа
ban=Бан
perm_timeout_text=Вы вошли как «{}»<br>Доступ открыт
temp_timeout_text=Вы вошли как «{}»<br>Доступ открыт на 8 часов
'''

HTML_DEFAULT = '''\
<!DOCTYPE html>
<head>
	<meta charset='utf-8'>
	<title>{page_title}</title>
	<style>
        html, body {{
            height: 100%;
            background-color: #eee;
            font-family: "Times New Roman", serif;
            font-size: 3vh;
            margin: 0 2vw 0 2vw;
        }}
        .container {{
            display: flex;
            justify-content: center;
            height: 100%;
            flex-direction: column;
            align-items: center;
            gap: 0vh;
        }}
        .info {{
            font-size: .5rem;
            font-family: Verdana, Geneva, Tahoma, sans-serif;
        }}
        /* Fix hr inside flex: */
        hr {{ width: min(46vh, 50vw); }}
	</style>
</head>
<body>
	<div class='container'>
		{message}
		<hr>
		<p class='info'>
			{ip_capt}: {ip_address}
			<br>{time_capt}: {timestamp}
			<br><a href='https://github.com/vikilpet/''>© https://github.com/vikilpet/</a>
			<br>
		</p>
	</div>
</body>
'''