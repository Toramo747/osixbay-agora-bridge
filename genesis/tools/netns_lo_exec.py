"""Dentro un namespace di rete vuoto (unshare -rn) attiva solo l'interfaccia loopback, poi esegue il comando.
Serve agli esempi di rete: localhost funziona, Internet no. Solo libreria standard (nessun bisogno di `ip`)."""
import fcntl, os, socket, struct, sys

SIOCGIFFLAGS, SIOCSIFFLAGS, IFF_UP = 0x8913, 0x8914, 0x1

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
flags = struct.unpack('16sH', fcntl.ioctl(s, SIOCGIFFLAGS, struct.pack('16sH', b'lo', 0))[:18])[1]
fcntl.ioctl(s, SIOCSIFFLAGS, struct.pack('16sH', b'lo', flags | IFF_UP))
s.close()
os.execv(sys.argv[1], sys.argv[1:])
