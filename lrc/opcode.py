import collections


class Operand(collections.namedtuple("Operand", "value ref")):
    MASK_REF = 2**12
    MASK_VAL = 2**12 - 1

    def __new__(cls, data):
        obj = super(Operand, cls).__new__(
                cls,
                value=(int(data) & Operand.MASK_VAL),
                ref=(int(data) & Operand.MASK_REF != 0),
                )

        return obj

    def __int__(self):
        value = self.value

        if self.ref:
            value += Operand.MASK_REF

        return value


class BaseOp(collections.namedtuple("BaseOp", "mneumonic opcode value lo hi")):
    def __new__(cls, mneumonic, opcode, value, lo=0, hi=0):
        return super(BaseOp, cls).__new__(cls, mneumonic, opcode, value, lo, hi)


class NullaryOp(BaseOp):
    def __new__(cls, data):
        return super(NullaryOp, cls).__new__(
                cls,
                mneumonic=cls.MNEUMONIC,
                opcode=cls.OPCODE,
                value=cls.OPCODE,
                )


class UnaryOp(BaseOp):
    def __new__(cls, data):
        lo = int(data)
        value = cls.OPCODE + (lo << 4)
        return super(UnaryOp, cls).__new__(
                cls,
                mneumonic=cls.MNEUMONIC,
                opcode=cls.OPCODE,
                value=value,
                lo=lo,
                )


class BinaryOp(BaseOp):
    def __new__(cls, data):
        lo, hi = data
        lo = int(lo)
        hi = int(hi)
        value = cls.OPCODE  + (int(lo) << 4) + (int(hi) << 20)
        return super(BinaryOp, cls).__new__(
                cls,
                mneumonic=cls.MNEUMONIC,
                opcode=cls.OPCODE,
                value=value,
                lo=lo,
                hi=hi,
                )


class Null(NullaryOp):
    MNEUMONIC = "NUL"
    OPCODE = 0


class Store(UnaryOp):
    MNEUMONIC = "STA"
    OPCODE = 1


class Load(UnaryOp):
    MNEUMONIC = "LDA"
    OPCODE = 2


class Increment(UnaryOp):
    MNEUMONIC = "INC"
    OPCODE = 3


class Decrement(UnaryOp):
    MNEUMONIC = "DEC"
    OPCODE = 4


class Addition(BinaryOp):
    MNEUMONIC = "ADD"
    OPCODE = 5


class Subtraction(BinaryOp):
    MNEUMONIC = "SUB"
    OPCODE = 6


class Jump(UnaryOp):
    MNEUMONIC = "JMP"
    OPCODE = 7


class Move(BinaryOp):
    MNEUMONIC = "MOV"
    OPCODE = 8


class Compare(BinaryOp):
    MNEUMONIC = "CMP"
    OPCODE = 9


class BranchAbove(UnaryOp):
    MNEUMONIC = "BRA"
    OPCODE = 10


class BranchBelow(UnaryOp):
    MNEUMONIC = "BRB"
    OPCODE = 11


class Halt(NullaryOp):
    MNEUMONIC = "HLT"
    OPCODE = 12


class Memory(object):
    ADDR_IO  =  0 # start of memory reserved for device I/O
    ADDR_REG = 17 # start of memory reserved for registers
    ADDR_FLG = 25 # start of memory reserved for flags
    ADDR_PRG = 33 # start of memory reserved for programs

    def __init__(self):
        self._ram = dict()
        self.ptr = Memory.ADDR_PRG

    def __len__(self):
        return max(self._ram) + 1 if self._ram else 0

    def __iter__(self):
        for index in range(len(self)):
            yield self.read(index)

    def read(self, index):
        assert 0 <= index
        return self._ram[index] if index in self._ram else 0

    def write(self, index, value):
        assert 0 <= index
        assert 0 <= value < 2**32
        self._ram[index] = value

    def read_eax(self):
        return self.read(Memory.ADDR_REG)

    def write_eax(self, value):
        self.write(Memory.ADDR_REG, value)

    @property
    def flag_cmp(self):
        return self.read(Memory.ADDR_FLG)

    @flag_cmp.setter
    def flag_cmp(self, val):
        self.write(Memory.ADDR_FLG, val)
