import sys, binascii, socket, select, ssl
import hashlib

class ApiRos:
	"Routeros api"
	def __init__(self, sk, print_debug:bool=False):
		self.sk = sk
		self.currenttag = 0
		self.print_debug = print_debug
	
	def d_print(self, msg:str):
		if not self.print_debug: return
		print(msg)

	def login(self, username, pwd):
		for repl, attrs in self.talk(
			["/login", "=name=" + username,
				"=password=" + pwd]):
			if repl == '!trap':
				return False
			elif '=ret' in attrs.keys():
				chal = binascii.unhexlify((attrs['=ret']).encode(sys.stdout.encoding))
				md = hashlib.md5()
				md.update(b'\x00')
				md.update(pwd.encode(sys.stdout.encoding))
				md.update(chal)
				for repl2, attrs2 in self.talk(["/login", "=name=" + username,
				"=response=00" + binascii.hexlify(md.digest()).decode(sys.stdout.encoding) ]):
						if repl2 == '!trap':
							return False
		return True

	def talk(self, words):
		if self.writeSentence(words) == 0: return
		r = []
		while 1:
			i = self.readSentence()
			if len(i) == 0: continue
			reply = i[0]
			attrs = {}
			for w in i[1:]:
				j = w.find('=', 1)
				if (j == -1):
					attrs[w] = ''
				else:
					attrs[w[:j]] = w[j+1:]
			r.append((reply, attrs))
			if reply == '!done': return r

	def writeSentence(self, words):
		ret = 0
		for w in words:
			self.writeWord(w)
			ret += 1
		self.writeWord('')
		return ret

	def readSentence(self):
		r = []
		while 1:
			w = self.readWord()
			if w == '': return r
			r.append(w)

	def writeWord(self, w):
		self.d_print(("<<< " + w))
		self.writeLen(len(w))
		self.writeStr(w)

	def readWord(self):
		ret = self.readStr(self.readLen())
		self.d_print((">>> " + ret))
		return ret

	def writeLen(self, l):
		if l < 0x80:
			self.writeByte((l).to_bytes(1, sys.byteorder))
		elif l < 0x4000:
			l |= 0x8000
			tmp = (l >> 8) & 0xFF
			self.writeByte(((l >> 8) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte((l & 0xFF).to_bytes(1, sys.byteorder))
		elif l < 0x200000:
			l |= 0xC00000
			self.writeByte(((l >> 16) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 8) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte((l & 0xFF).to_bytes(1, sys.byteorder))
		elif l < 0x10000000:
			l |= 0xE0000000
			self.writeByte(((l >> 24) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 16) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 8) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte((l & 0xFF).to_bytes(1, sys.byteorder))
		else:
			self.writeByte((0xF0).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 24) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 16) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte(((l >> 8) & 0xFF).to_bytes(1, sys.byteorder))
			self.writeByte((l & 0xFF).to_bytes(1, sys.byteorder))

	def readLen(self):
		c = ord(self.readStr(1))
		if (c & 0x80) == 0x00:
			pass
		elif (c & 0xC0) == 0x80:
			c &= ~0xC0
			c <<= 8
			c += ord(self.readStr(1))
		elif (c & 0xE0) == 0xC0:
			c &= ~0xE0
			c <<= 8
			c += ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
		elif (c & 0xF0) == 0xE0:
			c &= ~0xF0
			c <<= 8
			c += ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
		elif (c & 0xF8) == 0xF0:
			c = ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
			c <<= 8
			c += ord(self.readStr(1))
		return c

	def writeStr(self, str):
		n = 0
		while n < len(str):
			r = self.sk.send(bytes(str[n:], 'UTF-8'))
			if r == 0: raise RuntimeError("connection closed by remote end")
			n += r

	def writeByte(self, str):
		n = 0
		while n < len(str):
			r = self.sk.send(str[n:])
			if r == 0: raise RuntimeError("connection closed by remote end")
			n += r

	def readStr(self, length):
		ret = ''
		while len(ret) < length:
			s = self.sk.recv(length - len(ret))
			if s == b'': raise RuntimeError("connection closed by remote end")
			if s >= (128).to_bytes(1, "big") :
			   return s
			ret += s.decode(sys.stdout.encoding, "replace")
		return ret

def open_socket(dst, port, secure=False):
	s = None
	res = socket.getaddrinfo(dst, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
	af, socktype, proto, canonname, sockaddr = res[0]
	skt = socket.socket(af, socktype, proto)
	if secure:
		s = ssl.wrap_socket(skt, ssl_version=ssl.PROTOCOL_TLSv1_2, ciphers="ADH-AES128-SHA256")
	else:
		s = skt
	s.connect(sockaddr)
	return s

def main():
	s = None
	dst = sys.argv[1]
	user = "admin"
	passw = ""
	secure = True
	port = 0
	if len(sys.argv) == 4:
	  user = sys.argv[2]
	  passw = sys.argv[3]
	elif len(sys.argv) == 3:
	  user = sys.argv[2]

	if (port==0):
	  port = 8729 if secure else 8728

	s = open_socket(dst, port, secure)
	if s is None:
	  print ('could not open socket')
	  sys.exit(1)

	apiros = ApiRos(s);
	if not apiros.login(user, passw):
	  return

	inputsentence = []

	while 1:
		r = select.select([s, sys.stdin], [], [], None)
		if s in r[0]:
			x = apiros.readSentence()

		if sys.stdin in r[0]:
			l = sys.stdin.readline()
			l = l[:-1]
			if l == '':
				apiros.writeSentence(inputsentence)
				inputsentence = []
			else:
				inputsentence.append(l)

def rosapi_send(ip:str, port:int
, username:str, password:str
, cmd:list, print_debug:bool=False
, secure:bool=True):
	''' Send command via rosapi.
		Return (True, data) on success
		or (False, error text).
	'''
	try:
		soc = None
		port = 8729 if secure else 8728
		(af, socktype, proto
		, canonname, sockaddr) = socket.getaddrinfo(
			ip
			, port
			, socket.AF_UNSPEC
			, socket.SOCK_STREAM
		)[0]
		soc = socket.socket(af, socktype, proto)
		if secure:
			soc = ssl.wrap_socket(
				soc
				, ciphers="ADH:@SECLEVEL=0"
			)
		soc.connect(sockaddr)
	except Exception as e:
		return False, repr(e)
	try:
		apiros = ApiRos(soc, print_debug)
		apiros.login(
			username
			, password
		)
		r = apiros.talk(cmd)
		return True, r
	except Exception as e:
		return False, repr(e)

if __name__ == '__main__':
	main()