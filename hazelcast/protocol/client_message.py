"""
Client Message is the carrier framed data as defined below.
Any request parameter, response or event data will be carried in the payload.

0                   1                   2                   3
0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|R|                      Frame Length                           |
+-------------+---------------+---------------------------------+
|  Version    |B|E|  Flags    |               Type              |
+-------------+---------------+---------------------------------+
|                       CorrelationId                           |
+---------------------------------------------------------------+
|                        PartitionId                            |
+-----------------------------+---------------------------------+
|        Data Offset          |                                 |
+-----------------------------+                                 |
|                      Message Payload Data                    ...
|                                                              ...


"""
import binascii
import ctypes
import struct

from hazelcast.serialization import *

# constants
VERSION = 0
BEGIN_FLAG = 0x80
END_FLAG = 0x40
BEGIN_END_FLAG = BEGIN_FLAG | END_FLAG
LISTENER_FLAG = 0x01

PAYLOAD_OFFSET = 18
SIZE_OFFSET = 0

FRAME_LENGTH_FIELD_OFFSET = 0
VERSION_FIELD_OFFSET = FRAME_LENGTH_FIELD_OFFSET + INT_SIZE_IN_BYTES
FLAGS_FIELD_OFFSET = VERSION_FIELD_OFFSET + BYTE_SIZE_IN_BYTES
TYPE_FIELD_OFFSET = FLAGS_FIELD_OFFSET + BYTE_SIZE_IN_BYTES
CORRELATION_ID_FIELD_OFFSET = TYPE_FIELD_OFFSET + SHORT_SIZE_IN_BYTES
PARTITION_ID_FIELD_OFFSET = CORRELATION_ID_FIELD_OFFSET + INT_SIZE_IN_BYTES
DATA_OFFSET_FIELD_OFFSET = PARTITION_ID_FIELD_OFFSET + INT_SIZE_IN_BYTES
HEADER_SIZE = DATA_OFFSET_FIELD_OFFSET + SHORT_SIZE_IN_BYTES


def copy_bytes_into(src_buf, dst_buf, offset, length):
    ctypes.memmove(ctypes.byref(dst_buf, offset), src_buf, length)


class ClientMessage(object):
    def __init__(self, buff=None, payload_size=0):
        if buff:
            self._buffer = buff
            self._read_index = 0
        else:
            self._buffer = ctypes.create_string_buffer(HEADER_SIZE + payload_size)
            self.set_data_offset(HEADER_SIZE)
            self._write_index = 0
        self._retrable = False

    # HEADER ACCESSORS
    def get_correlation_id(self):
        return struct.unpack_from(FMT_LE_INT, self._buffer, CORRELATION_ID_FIELD_OFFSET)[0]

    def set_correlation_id(self, val):
        struct.pack_into(FMT_LE_INT, self._buffer, CORRELATION_ID_FIELD_OFFSET, val)
        return self

    def get_partition_id(self):
        return struct.unpack_from(FMT_LE_INT, self._buffer, PARTITION_ID_FIELD_OFFSET)[0]

    def set_partition_id(self, val):
        struct.pack_into(FMT_LE_INT, self._buffer, PARTITION_ID_FIELD_OFFSET, val)
        return self

    def get_message_type(self):
        return struct.unpack_from(FMT_LE_UINT16, self._buffer, TYPE_FIELD_OFFSET)[0]

    def set_message_type(self, val):
        struct.pack_into(FMT_LE_UINT16, self._buffer, TYPE_FIELD_OFFSET, val)
        return self

    def get_flags(self):
        return struct.unpack_from(FMT_LE_UINT8, self._buffer, FLAGS_FIELD_OFFSET)[0]

    def set_flags(self, val):
        struct.pack_into(FMT_LE_UINT8, self._buffer, FLAGS_FIELD_OFFSET, val)
        return self

    def get_frame_length(self):
        return struct.unpack_from(FMT_LE_INT, self._buffer, FRAME_LENGTH_FIELD_OFFSET)[0]

    def set_frame_length(self, val):
        struct.pack_into(FMT_LE_INT, self._buffer, FRAME_LENGTH_FIELD_OFFSET, val)
        return self

    def get_data_offset(self):
        return struct.unpack_from(FMT_LE_UINT16, self._buffer, DATA_OFFSET_FIELD_OFFSET)[0]

    def set_data_offset(self, val):
        struct.pack_into(FMT_LE_UINT16, self._buffer, DATA_OFFSET_FIELD_OFFSET, val)
        return self

    def __write_offset(self):
        return self.get_data_offset() + self._write_index

    def __read_offset(self):
        return self.get_data_offset() + self._read_index

    # PAYLOAD
    def append_byte(self, val):
        struct.pack_into(FMT_LE_UINT8, self._buffer, self.__write_offset(), val)
        self._write_index += BYTE_SIZE_IN_BYTES
        return self

    def append_bool(self, val):
        return self.append_byte(1 if val else 0)

    def append_int(self, val):
        struct.pack_into(FMT_LE_INT, self._buffer, self.__write_offset(), val)
        self._write_index += INT_SIZE_IN_BYTES
        return self

    def append_long(self, val):
        struct.pack_into(FMT_LE_LONG, self._buffer, self.__write_offset(), val)
        self._write_index += LONG_SIZE_IN_BYTES
        return self

    def append_str(self, val):
        self.append_byte_array(val.encode("utf-8"))
        return self

    def append_byte_array(self, arr):
        length = len(arr)
        # length
        self.append_int(length)
        # copy content
        copy_bytes_into(arr, self._buffer, self.__write_offset(), length)
        self._write_index += length

    # PAYLOAD READ
    def _read_from_buff(self, fmt, size):
        val = struct.unpack_from(fmt, self._buffer, self.__read_offset())
        self._read_index += size
        return val[0]

    def read_byte(self):
        return self._read_from_buff(FMT_LE_UINT8, BYTE_SIZE_IN_BYTES)

    def read_bool(self):
        return True if self.read_byte() else False

    def read_int(self):
        return self._read_from_buff(FMT_LE_INT, INT_SIZE_IN_BYTES)

    def read_long(self):
        return self._read_from_buff(FMT_LE_LONG, LONG_SIZE_IN_BYTES)

    def read_str(self):
        return self.read_byte_array().decode("utf-8")

    def read_byte_array(self):
        length = self.read_int()
        result = self._buffer[self.__read_offset(): self.__read_offset() + length]
        self._read_index += length
        return result

    # helpers

    def is_retryable(self):
        return self._retrable

    def set_retryable(self, val):
        self._retrable = val
        return self

    def is_complete(self):
        try:
            return (self.__read_offset() >= HEADER_SIZE) and (self.__read_offset() == self.get_frame_length())
        except AttributeError:
            return False

    def is_flag_set(self, flag):
        i = self.get_flags() & flag
        return i == flag

    def add_flag(self, flags):
        self.set_flags(self.get_flags() | flags)
        return self

    def update_frame_length(self):
        self.set_frame_length(self.__write_offset())
        return self

    def __repr__(self):
        return binascii.hexlify(self._buffer)

    def __str__(self):
        return "ClientMessage:{{" \
               "length={}, " \
               "correlationId={}, " \
               "messageType={}, " \
               "partitionId={}, " \
               "isComplete={}, " \
               "isRetryable={}, " \
               "isEvent={}, " \
               "writeOffset={}}}".format(self.get_frame_length(),
                                         self.get_correlation_id(),
                                         self.get_message_type(),
                                         self.get_partition_id(),
                                         self.is_complete(),
                                         self.is_retryable(),
                                         self.is_flag_set(LISTENER_FLAG),
                                         self.get_data_offset())