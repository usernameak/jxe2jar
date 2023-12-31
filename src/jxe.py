"""JXE class."""
# pylint: disable=W0612
import struct
from enum import Enum
from io import IOBase
from zipfile import ZipFile

from bitstring import BitArray
from common import ReaderStream, StreamCursor, WriterStream  # noqa: F401
# from bytecode import estimate_bc_size


class ConstType(int, Enum):
    """Constant types"""

    INT = 0
    STRING = 1
    CLASS = 2
    LONG = 3
    REF = 4


class J9ROMField:
    """J9 Field."""

    def __init__(self, name, signature, access_flag):
        self.name = name
        self.signature = signature
        self.access_flag = access_flag

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Field from stream."""
        name = stream.read_string_ref()
        signature = stream.read_string_ref()
        # print(name + signature)
        access_flags = stream.read_u32()

        if access_flags & 0x400000:
            stream.read_u32()
            if access_flags & 0x40000:
                stream.read_u32()

        if access_flags & 0x40000000:
            stream.read_u32()

        return J9ROMField(name, signature, access_flags)


class J9ROMCatchException:
    """J9 Catch Exception."""

    def __init__(self, start, end, handler, catch_type):
        self.start = start
        self.end = end
        self.handler = handler
        self.catch_type = catch_type

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Catch Exception from stream."""
        start = stream.read_u32()
        end = stream.read_u32()
        handler = stream.read_u32()
        catch_type = stream.read_u32()
        return J9ROMCatchException(start, end, handler, catch_type)


class J9ROMThrowException:
    """J9 Throw Exception."""

    def __init__(self, throw_type):
        self.throw_type = throw_type

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Throw Exception"""
        return J9ROMThrowException(stream.read_string_ref())


class J9ROMMethod:
    """J9 MMethod."""

    def __init__(
        self,
        name,
        signature,
        modifier,
        max_stack,
        arg_count,
        temp_count,
        bytecode,
        catch_exceptions,
        throw_exceptions,
    ):
        self.name = name
        self.signature = signature
        self.modifier = modifier
        self.max_stack = max_stack
        self.arg_count = arg_count
        self.temp_count = temp_count
        self.bytecode = bytecode
        self.catch_exceptions = catch_exceptions
        self.throw_exceptions = throw_exceptions

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Method."""
        # print(stream.get())
        name = stream.read_string_ref()
        # print('name: ' + name)
        signature = stream.read_string_ref()
        # print('sig: ' + signature)
        modifier = stream.read_u32()
        use_bytecodesize_high = modifier & 0x00008000
        # add_four1 = modifier & 0x02000000
        has_bytecode_extra = modifier & 0x00020000
        # add_four2 = modifier & 0x00400000
        add_four1 = modifier & 0x00010000
        max_stack = stream.read_u16()
        if modifier & 0x100:
            base = stream.get()  # noqa: F841
            native_arg_count = stream.read_u8()  # noqa: F841
            temp_count = stream.read_u8()
            stream.read_u8()  # noqa: F841
            arg_count2 = stream.read_u8()
            stream.read_u8()
            stream.read_u8()
            arg_count = stream.read_u8()
            return_type = stream.read_u8()  # noqa: F841
            args = []
            for i in range(arg_count):
                args.append(stream.read_u8())
                
            # align
            stream.set((stream.get() + 3) & ~3)
            # stream.read_u32()
            if modifier & 0x2000000:
                stream.read_u32()
            if modifier & 0x20000:
                stream.read_bytes(stream.read_u16() * 16 + 4 * stream.read_u16())
            caught_exceptions = []
            thrown_exceptions = []
            bytecode = stream.read_bytes(0)
            print("Native method", stream.get(), hex(modifier), arg_count, name)
            

        else:
            bytecode_size_low = stream.read_u16()
            bytecode_size_high = stream.read_u8()
            arg_count = stream.read_u8()
            temp_count = stream.read_u16()
            bytecode_size = bytecode_size_low
            if use_bytecodesize_high:
                bytecode_size += bytecode_size_high << 16
            # print("bc size %d" % bytecode_size)
            # print("argcnt %d" % arg_count)
            # print("bc size est %d" % estimate_bc_size(stream, bytecode_size_low - 6))
            bytecode = stream.read_bytes(bytecode_size)
            stream.set((stream.get() + 3) & ~3)
            if has_bytecode_extra:
                caught_exception_count = stream.read_u16()
                thrown_exception_count = stream.read_u16()
                caught_exceptions = [
                    J9ROMCatchException.read(stream)
                    for i in range(caught_exception_count)
                ]
                thrown_exceptions = [
                    J9ROMThrowException.read(stream)
                    for i in range(thrown_exception_count)
                ]
            else:
                caught_exceptions = []
                thrown_exceptions = []

            # if add_four2:
            # stream.read_u32()

        return J9ROMMethod(
            name,
            signature,
            modifier,
            max_stack,
            arg_count,
            temp_count,
            bytecode,
            caught_exceptions,
            thrown_exceptions,
        )


class J9ROMInterface:
    """J9 Interface."""

    def __init__(self, name):
        self.name = name

    @staticmethod
    def read(stream: BitArray):
        """ "Returns J9 Interface from stream."""
        name = stream.read_string_ref()
        return J9ROMInterface(name)


class J9ROMConstant:
    """J9 Constant."""

    def __init__(self, cons_type, value=None, _class=None, name=None, descriptor=None):
        self.type = cons_type
        match cons_type:
            case ConstType.INT | ConstType.STRING | ConstType.LONG:
                self.value = value
            case ConstType.CLASS:
                self.value = value
            case ConstType.REF:
                self._class = _class
                self.name = name
                self.descriptor = descriptor

    @staticmethod
    def read(stream: BitArray, base):
        """Returns J9 constant from stream."""
        pos = stream.get()
        value = stream.read_u32()
        value_type = stream.read_u32()

        match value_type:
            case ConstType.STRING | ConstType.CLASS:
                value = struct.unpack("<i", struct.pack("<I", value))[0]
                ptr = pos + value
                with StreamCursor(stream, ptr):
                    value = stream.read_string()
            case ConstType.INT:
                value = struct.pack("<I", value)
            case _:
                class_ptr = base + 8 * value
                try:
                    with StreamCursor(stream, class_ptr):
                        _class = stream.read_string_ref()
                    ptr = value_type + pos + 4
                    with StreamCursor(stream, ptr):
                        name = stream.read_string_ref()
                        descriptor = stream.read_string_ref()
                    return J9ROMConstant(
                        ConstType.REF, _class=_class, name=name, descriptor=descriptor
                    )
                except Exception as exc:
                    value = struct.pack("<II", value, value_type)
                    value_type = 3
                    print(exc)

        return J9ROMConstant(value_type, value=value)


class J9ROMClass:
    """J9 Class."""

    def __init__(
        self,
        minor,
        major,
        class_name,
        superclass_name,
        access_flags,
        interfaces,
        methods,
        fields,
        constant_pool,
    ):
        self.minor = minor
        self.major = major
        self.class_name = class_name
        self.superclass_name = superclass_name
        self.access_flags = access_flags
        self.interfaces = interfaces
        self.methods = methods
        self.fields = fields
        self.constant_pool = constant_pool

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Class from stream."""
        class_name = stream.read_string_ref()
        class_pointer = stream.read_relative()

        with StreamCursor(stream, class_pointer):
            rom_size = stream.read_u32()  # noqa: F841
            single_scalar_static_count = stream.read_u32()  # noqa: F841
            class_name = stream.read_string_ref()
            print(class_name)
            superclass_name = stream.read_string_ref()
            access_flags = stream.read_u32()
            interface_count = stream.read_u32()
            interfaces_pointer = stream.read_relative()

            with StreamCursor(stream, interfaces_pointer):
                interfaces = [
                    J9ROMInterface.read(stream) for i in range(interface_count)
                ]

            rom_method_count = stream.read_u32()
            rom_methods_pointer = stream.read_relative()

            with StreamCursor(stream, rom_methods_pointer):
                methods = [J9ROMMethod.read(stream) for i in range(rom_method_count)]

            rom_field_count = stream.read_u32()
            rom_fields_pointer = stream.read_relative()

            with StreamCursor(stream, rom_fields_pointer):
                fields = [J9ROMField.read(stream) for i in range(rom_field_count)]

            object_static_count = stream.read_u32()  # noqa: F841
            double_scalar_static_count = stream.read_u32()  # noqa: F841
            ram_constant_pool_count = stream.read_u32()  # noqa: F841
            rom_constant_pool_count = stream.read_u32()
            crc = stream.read_u32()  # noqa: F841
            instance_size = stream.read_u32()  # noqa: F841
            instance_shape = stream.read_u32()  # noqa: F841
            cp_shape_description_pointer = stream.read_relative()  # noqa: F841
            outer_class_name = stream.read_relative()  # noqa: F841
            member_access_flags = stream.read_u32()  # noqa: F841
            inner_class_count = stream.read_u32()  # noqa: F841
            inner_classes_pointer = stream.read_relative()  # noqa: F841
            major = stream.read_u16()
            minor = stream.read_u16()
            optional_flags = stream.read_u32()
            optional_info_pointer = stream.read_relative()

            if not optional_flags & 0x2000:
                with StreamCursor(stream, optional_info_pointer):
                    pass
                    # source_filename = stream.read_sprr(optional_flags, 0x1)
                    # generic_signature = stream.read_sprr(optional_flags, 0x2)
                    # source_debug_ext = stream.read_sprr(optional_flags, 0x4)
                    # annotation_info = stream.read_sprr(optional_flags, 0x8)
                    # debug_info = stream.read_sprr(optional_flags, 0x10)
                    # enclosing_method = stream.read_sprr(optional_flags, 0x40)
                    # simple_name = stream.read_sprr(optional_flags, 0x80)

            base = stream.get()
            constant_pool_count = rom_constant_pool_count
            constant_pool = []

            for i in range(constant_pool_count):
                try:
                    constant_pool.append(J9ROMConstant.read(stream, base))
                except EOFError:
                    # Usual between ram_constant_pool_count and rom_constant_pool_count
                    # liy double const but in some cases last element contain not valid
                    # string const, so we skip sthis case
                    pass

        return J9ROMClass(
            minor,
            major,
            class_name,
            superclass_name,
            access_flags,
            interfaces,
            methods,
            fields,
            constant_pool,
        )


class J9ROMImage:
    """J9 Image."""

    def __init__(self, signature, flags_and_version, rom_size, symbol_file_id, classes):
        self.signature = signature
        self.flags_and_version = flags_and_version
        self.rom_size = rom_size
        self.symbol_file_id = symbol_file_id
        self.classes = classes

    @staticmethod
    def read(stream: BitArray):
        """Returns J9 Image from stream."""
        signature = stream.read_u32()
        flags_and_version = stream.read_u32()
        rom_size = stream.read_u32()
        class_count = stream.read_u32()
        jxe_pointer = stream.read_relative()  # noqa: F841
        toc_pointer = stream.read_relative()
        first_class_pointer = stream.read_relative()  # noqa: F841
        aot_pointer = stream.read_relative()  # noqa: F841
        symbol_file_id = stream.read_bytes(0x10)
        pos = stream.get()
        stream.set(toc_pointer)
        classes = [J9ROMClass.read(stream) for i in range(class_count)]
        stream.set(pos)

        return J9ROMImage(
            signature, flags_and_version, rom_size, symbol_file_id, classes
        )


class JXE:
    """JXE object."""

    def __init__(self, image):
        self.image = image

    @staticmethod
    def read(stream: IOBase):
        """Returns JXE class from file object reading."""
        with ZipFile(stream.file_object) as fp_zipfile:
            with fp_zipfile.open("rom.classes") as rom:
                rom_stream = ReaderStream.bytes_to_stream(rom.read())
                return JXE(J9ROMImage.read(rom_stream))
