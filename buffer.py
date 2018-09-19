
from struct import pack, unpack


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

    def insert_string(self, s, encoding='utf-8'):
        self.insert_raw((s + chr(0)).encode(encoding))


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

    def get_dword(self):
        return unpack('<L', self.get_raw(4))[0]

    def get_long(self):
        return unpack('<Q', self.get_raw(8))[0]

    def get_string(self, encoding='utf-8'):
        r = self.get_raw(self.data.index(b'\00', self.position) - self.position).decode(encoding)
        self.position += 1
        return r
