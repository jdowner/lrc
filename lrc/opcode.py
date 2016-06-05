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
