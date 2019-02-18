import struct

class DeserialError(Exception):
    pass

class Deserializer:

    def __init__(self, data):
        self._data = data

    def __bool__(self):
        return len(self._data) > 0

    def read_string(self):
        if len(self._data) < 1:
            raise DeserialError
        string_size = self._data[0]
        if len(self._data) < 1 + string_size:
            raise DeserialError
        string = self._data[1:1 + string_size].decode('ascii')
        self._data = self._data[1 + string_size:]
        return string

    def read_fixed_string(self, size):
        if len(self._data) < size:
            raise DeserialError
        string = self._data[:size].decode('ascii').rstrip('\0')
        self._data = self._data[size:]
        return string

    def _read_value(self, value_size, format_type):
        if len(self._data) < value_size:
            raise DeserialError
        result = struct.unpack('!' + format_type, self._data[:value_size])[0]
        self._data = self._data[value_size:]
        return result

    def read_byte(self):
        return self._read_value(1, 'B')

    def read_2_bytes(self):
        return self._read_value(2, 'H')

    def read_4_bytes(self):
        return self._read_value(4, 'I')

    def read_data(self):
        data_size = self.read_2_bytes()
        if len(self._data) < data_size:
            raise DeserialError
        data = self._data[:data_size]
        self._data = self._data[data_size:]
        return data

    def remaining_data(self):
        return self._data

class Serializer:

    def __init__(self):
        self._fragments = []

    def write_string(self, string):
        self._fragments.append(bytes([len(string)]))
        self._fragments.append(string.encode('ascii'))

    def write_fixed_string(self, string, size):
        assert len(string) <= size
        string += '\0' * (size - len(string))
        self._fragments.append(string.encode('ascii'))

    def write_byte(self, value):
        self._fragments.append(bytes([value]))

    def write_2_bytes(self, value):
        self._fragments.append(struct.pack('!H', value))

    def write_4_bytes(self, value):
        self._fragments.append(struct.pack('!I', value))

    def write_data(self, data):
        self.write_2_bytes(len(data))
        self._fragments.append(data)

    def append(self, data):
        self._fragments.append(data)

    def result(self):
        return b''.join(self._fragments)

