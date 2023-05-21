import struct
from enum import Enum


class CONST(bytes, Enum):
    CLASS = b"\x07"
    FIELDREF = b"\x09"
    METHODREF = b"\x0a"
    INTERFACEMETHODREF = b"\x0b"
    STRING = b"\x08"
    INTEGER = b"\x03"
    FLOAT = b"\x04"
    LONG = b"\x05"
    DOUBLE = b"\x06"
    NAMEANDTYPE = b"\x0c"
    UTF8 = b"\x01"


class J9CONST(int, Enum):
    INT = 0
    STRING = 1
    CLASS = 2
    LONG = 3
    REF = 4


class ConstPool:
    def __init__(self, romclass):
        self.pool = []
        self.transform = {}
        stack = []
        # self.pool.append([-1, None])

        for i, constant in enumerate(romclass.constant_pool):
            if constant.type == J9CONST.INT:
                index = len(self.pool)
                self.pool.append([CONST.INTEGER, constant.value])
                self.transform[i] = {"new_index": index, "type": CONST.INTEGER}
            elif constant.type == J9CONST.LONG:
                index = len(self.pool)
                self.pool.append([CONST.DOUBLE, constant.value[::-1]])
                self.pool.append([-1, None])
                self.transform[i] = {"new_index": index, "type": CONST.DOUBLE}
            elif constant.type == J9CONST.STRING:
                index = len(self.pool)
                self.pool.append([CONST.STRING, ""])
                value = constant.value.encode("utf-8")
                stack.append(
                    (
                        index,
                        CONST.UTF8,
                        struct.pack(">H", len(value)) + value,
                    )
                )
                self.transform[i] = {"new_index": index, "type": CONST.STRING}
            elif constant.type == J9CONST.CLASS:
                index = len(self.pool)
                self.pool.append([CONST.CLASS, ""])
                value = constant.value.encode("utf-8")
                stack.append(
                    (
                        index,
                        CONST.UTF8,
                        struct.pack(">H", len(value)) + value,
                    )
                )
                self.transform[i] = {"new_index": index, "type": CONST.CLASS}
            elif constant.type == J9CONST.REF:
                index = len(self.pool)
                const_type = (
                    CONST.METHODREF
                    if constant.descriptor.find("(") >= 0
                    else CONST.FIELDREF
                )
                self.pool.append([const_type, "", ""])
                value_class = constant._class.encode("utf-8")
                value_c_name = constant.name.encode("utf-8")
                value_c_desc = constant.descriptor.encode("utf-8")
                stack.append(
                    (
                        index,
                        CONST.CLASS,
                        struct.pack(">H", len(value_class)) + value_class,
                    )
                )
                stack.append(
                    (
                        index,
                        CONST.NAMEANDTYPE,
                        struct.pack(">H", len(value_c_name)) + value_c_name,
                        struct.pack(">H", len(value_c_desc)) + value_c_desc,
                    )
                )
                self.transform[i] = {"new_index": index, "type": const_type}

        for elem in stack:
            cp_id = len(self.pool)
            if elem[1] == CONST.UTF8:
                self.pool.append([elem[1], elem[2]])
                if self.pool[elem[0]][1]:
                    self.pool[elem[0]][2] = struct.pack(">H", cp_id + 1)
                else:
                    self.pool[elem[0]][1] = struct.pack(">H", cp_id + 1)
            elif elem[1] == CONST.CLASS:
                self.pool.append([elem[1], ""])
                stack.append((cp_id, CONST.UTF8, elem[2]))
                self.pool[elem[0]][1] = struct.pack(">H", cp_id + 1)
            elif elem[1] == CONST.NAMEANDTYPE:
                self.pool.append([elem[1], "", ""])
                stack.append((cp_id, CONST.UTF8, elem[2]))
                stack.append((cp_id, CONST.UTF8, elem[3]))
                self.pool[elem[0]][2] = struct.pack(">H", cp_id + 1)

    def add(self, value_type, value):
        if isinstance(value, str):
            value = value.encode("utf-8")

        if value_type == CONST.CLASS:
            index = len(self.pool)
            self.pool.append([CONST.UTF8, struct.pack(">H", len(value)) + value])
            self.pool.append([CONST.CLASS, struct.pack(">H", index + 1)])
            return index + 2

        if value_type == CONST.UTF8:
            index = len(self.pool)
            self.pool.append([CONST.UTF8, struct.pack(">H", len(value)) + value])
            return index + 1

        raise ValueError(f"Unexpected value type: '{value_type}'")

    def apply_transform(self, index, transform_type):
        self.pool[index][0] = transform_type

    def check_transform(self, index, transform_type=None):
        return index in self.transform and (
            transform_type and self.transform[index]["type"] == b"\x06"
        )

    def get_transform(self, index):
        return self.transform[index]

    def write(self, stream):
        stream.write_u16(len(self.pool) + 1)
        for elem in self.pool:
            if elem[0] == -1:
                continue
            stream.write_raw_bytes(elem[0])
            stream.write_raw_bytes(elem[1])
            if len(elem) > 2:
                stream.write_raw_bytes(elem[2])
