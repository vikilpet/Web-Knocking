### Web Knocking

## How it works
It is a web server written in Python.

If the request is *good*, then the IP address of the person who made the request is added to the white list on the router. IP addresses of *bad* requests are blacklisted.

It is assumed that for the white list you allow something, and for the black list you block any incoming connections.

For users who need to connect outside the office, we give a link like this:

	http://100.200.1.2:1212/access?SeCrEtCoDe


## Setup
### Option 1: EXE
Just download the archive from the release page.

### Option 2: Python
**Requirements:** Python 3.8; Windows 7+

Theoretically it should also work on Linux, but I haven't checked.

Download the project, install the dependencies:

	pip install -r requirements.txt

## Usage
Change settings in *settings.ini* to your own.

Forward a port in the router from the settings to the computer where Web Knocking is running.

Enable API access on the router from this computer (*ip services - api-ssl* or *api*).

For white and black lists, make the rules according to your needs. For example, forward port 80 for white list on MikroTik:

	/ip firewall nat add src-address-list=white_list in-interface=WAN \
	dst-port=80 action=dst-nat to-addresses=192.168.0.10 to-ports=80

## Project Support
- [Donate via PayPal](https://www.paypal.me/vikil)
