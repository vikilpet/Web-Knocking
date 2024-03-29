# Web Knocking для MikroTik
![Screenshot](https://user-images.githubusercontent.com/43970835/147935163-3ebf16d4-4c15-44b2-baec-ee854becf0e4.png)

## Как это работает
Это веб-сервер на Python.

Если запрос *правильный*, то IP-адрес того, кто сделал этот запрос, добавляется в *белый список* на маршрутизаторе. IP-адреса *плохих* запросов попадают в *чёрный список*.

Предполагается, что для белого списка вы что-то разрешаете, а для чёрного списка блокируются любые входящие соединения.

Пользователям, которым нужно подключиться вне офиса, даём ссылку вида:

	http://100.100.1.2:2020/access_SeCrEtCoDe

Теоретически можно сделать и для других устройств с помощью [netmiko](https://github.com/ktbyers/netmiko), но мне не на чём проверить.

## Установка
### Вариант 1: EXE
Просто скачайте архив со страницы [релизов](https://github.com/vikilpet/Web-Knocking/releases).

### Вариант 2: Python
**Требования:** Python 3.8; Windows 7+

Теоретически должно работать и на Linux, но я не проверял.

Просто скачайте [проект](https://github.com/vikilpet/Web-Knocking/releases). Без зависимостей от нестандартных модулей.

## Использование
Измените настройки в *settings.ini* на свои.

Очень рекомендуется добавить свой IP адрес в *safe_hosts*, чтобы при тестировании не занести себя в чёрный список. С адресов из списка *safe_hosts* можно выполнить запрос на перезагрузку настроек вида `http://ip:port/reload`

Пробросьте в маршрутизаторе порт из настроек на компьютер, на котором запущен Web Knocking.

Включите в маршрутизаторе доступ к API с этого компьютера (*ip services - api-ssl* или *api*).

Для белого и чёрного списка настройте правила в соответствии с вашими нуждами. Например проброс 80 порта для MikroTik:

	/ip firewall nat add src-address-list=white_list in-interface=WAN \
	dst-port=80 action=dst-nat to-addresses=192.168.0.10 to-ports=80

### Только для Windows:
В консоли:
- нажмите «i» для вывода списка IP адресов;
- «u» для вывода списка пользователей (истекшие даты помечены звездочкой);
- «s» для перезагрузки настроек, чтобы добавлять пользователей без перезапуска.

## Помощь проекту
- Расскажите о проекте друзьям
- Присылайте отчёты об ошибках
