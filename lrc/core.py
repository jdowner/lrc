import collections


class Terminate(Exception):
    pass


class SegmentationFault(Exception):
    pass


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


class Opcode(collections.namedtuple("Opcode", "mneumonic opcode value lo hi")):
    """
    Each instruction is designed to be 32 bits long with the following
    structure,

        OOOOLLLLLLLLLLLLLLLLHHHHHHHHHHHHHHHH

        O: instruction
        L: 'lo' operand
        H: 'hi' operand

    """

    def __new__(cls, lo, hi):
        value = (cls.OPCODE << 28) + (int(lo) << 14) + int(hi)
        return super(Opcode, cls).__new__(
                cls,
                cls.MNEUMONIC,
                cls.OPCODE,
                value,
                int(lo),
                int(hi),
                )


class Null(Opcode):
    MNEUMONIC = "NUL"
    OPCODE = 0

    def execute(self, memory):
        pass


class Store(Opcode):
    MNEUMONIC = "STA"
    OPCODE = 1

    def execute(self, memory):
        val = memory.read_eax()
        memory.write(self.lo, val)


class Load(Opcode):
    MNEUMONIC = "LDA"
    OPCODE = 2

    def execute(self, memory):
        memory.write_eax(self.lo)


class Increment(Opcode):
    MNEUMONIC = "INC"
    OPCODE = 3

    def execute(self, memory):
        val = memory.read(self.lo)
        memory.write(self.lo, val + 1)


class Decrement(Opcode):
    MNEUMONIC = "DEC"
    OPCODE = 4

    def execute(self, memory):
        val = memory.read(self.lo)
        memory.write(self.lo, val - 1)


class Addition(Opcode):
    MNEUMONIC = "ADD"
    OPCODE = 5

    def execute(self, memory):
        val = (memory.read(self.lo) + memory.read(self.hi)) % 2**16
        memory.write(self.lo, val)


class Subtraction(Opcode):
    MNEUMONIC = "SUB"
    OPCODE = 6

    def execute(self, memory):
        val = (memory.read(self.lo) - self.hi) % 2**16
        memory.write(self.lo, val)


class Jump(Opcode):
    MNEUMONIC = "JMP"
    OPCODE = 7

    def execute(self, memory):
        memory.ptr = self.lo - 1


class Move(Opcode):
    MNEUMONIC = "MOV"
    OPCODE = 8

    def execute(self, memory):
        val = memory.read(self.hi)
        memory.write(self.lo, val)


class Compare(Opcode):
    MNEUMONIC = "CMP"
    OPCODE = 9

    def execute(self, memory):
        vlo = memory.read(self.lo)
        vhi = memory.read(self.hi)
        memory.flag_cmp = 1 if vlo < vhi else 0


class BranchAbove(Opcode):
    MNEUMONIC = "BRA"
    OPCODE = 10

    def execute(self, memory):
        if memory.flag_cmp == 0:
            memory.ptr = self.lo - 1


class BranchBelow(Opcode):
    MNEUMONIC = "BRB"
    OPCODE = 11

    def execute(self, memory):
        if memory.flag_cmp == 1:
            memory.ptr = self.lo - 1


class Halt(Opcode):
    MNEUMONIC = "HLT"
    OPCODE = 12

    def execute(self, memory):
        raise Terminate()


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

    def load_program(self, prog):
        for index, instruction in zip(range(len(prog)), prog):
            self.write(Memory.ADDR_PRG + index, instruction.value)

    @property
    def flag_cmp(self):
        return self.read(Memory.ADDR_FLG)

    @flag_cmp.setter
    def flag_cmp(self, val):
        self.write(Memory.ADDR_FLG, val)
