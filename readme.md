# Web Knocking for MikroTik
![Screenshot](https://user-images.githubusercontent.com/43970835/147935163-3ebf16d4-4c15-44b2-baec-ee854becf0e4.png)

## How it works
This is a web server written in Python

If the request is *good* then the IP address of the person who made the request is added to the white list on the router. IP addresses of *bad* requests are blacklisted.

It is assumed that for the white list you allow something and for the black list you block any incoming connections.

For users who need to connect outside the office we give a link like this:

	http://100.100.1.2:2020/access_SeCrEtCoDe

It is possible to support other vendors' devices with help of [netmiko](https://github.com/ktbyers/netmiko) but I only have MikroTik-s.

## Setup
### Option 1: EXE
Just download the archive from the release page.

### Option 2: Python
**Requirements:** Python 3.8; Windows 7+

It should also work on Linux but I haven't checked.

Just download the project. No third-party dependencies.

## Usage
Change settings in *settings.ini* to your own.

It is highly recommended to add your IP address to *safe_hosts* to avoid blacklisting during testing. From the addresses on the *safe_hosts* list you can request a reload of the settings with url `http://ip:port/reload`

Forward a port in the router from the settings to the computer where Web Knocking is running.

Enable API access on the router from this computer (*ip services - api-ssl* or *api*).

For white and black lists make the rules according to your needs. For example forward port 80 for white list on MikroTik:

	/ip firewall nat add src-address-list=white_list in-interface=WAN \
	dst-port=80 action=dst-nat to-addresses=192.168.0.10 to-ports=80

### Only in Windows:
In console window:
- press «i» to print out IP addresses;
- «u» to print out users (expired dates are marked with an asterisk);
- «s» to reload settings so you can add new users without restart.

## Support project
- [Donate via PayPal](https://www.paypal.me/vikil)
- Correct my mistakes
