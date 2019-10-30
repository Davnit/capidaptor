
from struct import pack, unpack


def format_buffer(buff):
    """Formats a data buffer as byte values and characters."""
    if len(buff) == 0:
        return

    if isinstance(buff, (DataBuffer, DataReader)):
        data = buff.data
    elif not isinstance(buff, (bytes, bytearray)):
        raise TypeError("Buffer must be a bytes-based object.")
    else:
        data = buff

    data_length = len(data)
    mod = data_length % 16

    ret = ''
    # Format _most_ of the buffer.
    for i in range(0, len(data)):
        if i != 0 and i % 16 == 0:
            ret += '\t'
            # 16 bytes at a time
            for j in range(i - 16, i):
                ret += ('.' if data[j] < 0x20 or data[j] > 0x7F else chr(data[j]))
            ret += '\n'

        ret += ('00' + hex(data[i])[2:])[-2:] + ' '

    # If the buffer length isn't a multiple of 16, add padding.
    if mod != 0:
        ret = ret.ljust(len(ret) + ((16 - mod) * 3))
        j = (data_length - mod)
    else:
        j = data_length - 16

    ret += '\t'

    # Finish the line
    for j in range(j, data_length):
        ret += ('.' if data[j] < 0x20 or data[j] > 0x7F else chr(data[j]))
    return ret + '\n'


class DataBuffer:
    def __init__(self):
        self.data = b''

    def __len__(self):
        return len(self.data)

    def insert_raw(self, data):
        self.data = self.data + data

    def insert_byte(self, byte):
        self.insert_raw(pack('<B', byte))

    def insert_word(self, word):
        self.insert_raw(pack('<H', word))

    def insert_dword(self, dword):
        if type(dword) == str:
            self.insert_raw(dword[::-1].encode('ascii'))
        else:
            self.insert_raw(pack('<L', dword))

    def insert_long(self, long):
        self.insert_raw(pack('<Q', long))

    def insert_string(self, s, encoding='utf-8', errors=None):
        self.insert_raw((s + chr(0)).encode(encoding, errors or 'strict'))


class DataReader:
    def __init__(self, data):
        self.data = data
        self.position = 0

    def __len__(self):
        return len(self.data)

    def get_raw(self, length=-1):
        if length == -1:
            length = (len(self.data) - self.position)

        r = self.data[self.position:(self.position + length)]
        self.position = self.position + length
        return r

    def get_byte(self):
        return unpack('<B', self.get_raw(1))[0]

    def get_word(self):
        return unpack('<H', self.get_raw(2))[0]

    def get_dword(self, as_str=False):
        val = self.get_raw(4)
        return val.decode('ascii')[::-1] if as_str else unpack('<L', val)[0]

    def get_long(self):
        return unpack('<Q', self.get_raw(8))[0]

    def get_string(self, encoding='utf-8', errors=None):
        r = self.get_raw(self.data.index(b'\00', self.position) - self.position).decode(encoding, errors or 'strict')
        self.position += 1
        return r
