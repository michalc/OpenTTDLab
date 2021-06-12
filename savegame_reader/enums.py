import enum

FIELD_TYPE_HAS_LENGTH_FIELD = 0x10


class FieldType(enum.IntEnum):
    END = 0
    I8 = 1
    U8 = 2
    I16 = 3
    U16 = 4
    I32 = 5
    U32 = 6
    I64 = 7
    U64 = 8
    STRINGID = 9
    STRING = 10
    STRUCT = 11
