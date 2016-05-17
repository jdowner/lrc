import asyncio
import logging
import sys

logger = logging.getLogger(__name__)


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
        return self.read(17)

    def write_eax(self, value):
        self.write(17, value)

    def set_flag(self, val):
        self.write(25, val)

    def flag(self):
        return self.read(25)


class BaseOp(object):
    def __init__(self, lo=0, hi=0):
        self._lo = lo
        self._hi = hi

    @property
    def lo(self):
        return self._lo

    @property
    def hi(self):
        return self._hi

    @property
    def mneumonic(self):
        return self.__class__.MNEUMONIC

    @property
    def opcode(self):
        return self.__class__.OPCODE


class NullaryOp(BaseOp):
    @property
    def value(self):
        return self.opcode


class UnaryOp(BaseOp):
    @property
    def value(self):
        return self.opcode + (self.lo << 4)


class BinaryOp(BaseOp):
    @property
    def value(self):
        return self.opcode + (self.lo << 4) + (self.hi << 20)


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


class Interpreter(object):
    def __init__(self):
        self.opcodes = {
                Load.OPCODE:        self._load,
                Increment.OPCODE:   self._increment,
                Store.OPCODE:       self._store,
                Decrement.OPCODE:   self._decrement,
                Addition.OPCODE:    self._addition,
                Subtraction.OPCODE: self._subtraction,
                Jump.OPCODE:        self._jump,
                Move.OPCODE:        self._move,
                }

    def run(self, memory):
        loop = asyncio.get_event_loop()

        @asyncio.coroutine
        def shutdown():
            for task in asyncio.Task.all_tasks():
                task.cancel()

            loop.call_soon(loop.stop)

        @asyncio.coroutine
        def tick():
            data = memory.read(memory.ptr)
            if data == 0:
                loop.create_task(shutdown())
                return

            opcode, data = self.interpret(data)
            self.opcodes[opcode](memory, data)

            memory.ptr += 1

            loop.create_task(tick())

        loop.create_task(tick())
        loop.run_forever()

    def interpret(self, data):
        mask_ins = 2**4 - 1
        mask_dat = 2**32 - 1

        opcode = data & mask_ins
        data = (data >> 4) & mask_dat

        return opcode, data

    def _load(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask
        memory.write_eax(lo)

    def _increment(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask

        val = memory.read(lo)
        memory.write(lo, val + 1)

    def _decrement(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask

        val = memory.read(lo)
        memory.write(lo, val - 1)

    def _store(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask

        val = memory.read_eax()
        memory.write(lo, val)

    def _addition(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask
        hi = (data >> 16) & mask

        val = (memory.read(lo) + memory.read(hi)) % 2**16
        memory.write(lo, val)

    def _subtraction(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask
        hi = (data >> 16) & mask

        val = (memory.read(lo) - hi) % 2**16
        memory.write(lo, val)

    def _jump(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask
        memory.ptr = lo - 1

    def _move(self, memory, data):
        mask = 2**16 - 1
        lo = data & mask
        hi = (data >> 16) & mask

        val = memory.read(hi)
        memory.write(lo, val)



def main(argv=sys.argv[1:]):
    memory = Memory()

    memory.write(Memory.ADDR_PRG + 0, Increment(5).value)
    memory.write(Memory.ADDR_PRG + 1, Store(5,6).value)
    memory.write(Memory.ADDR_PRG + 2, Increment(6).value)
    memory.write(Memory.ADDR_PRG + 3, Decrement(5).value)

    memory.write(Memory.ADDR_PRG + 4, Jump(8).value)
    memory.write(Memory.ADDR_PRG + 8, Addition(6,2).value)

    interpreter = Interpreter()
    interpreter.run(memory)

    for addr in memory:
        print(addr)


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)

    main()
