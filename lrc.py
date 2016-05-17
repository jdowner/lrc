#!/usr/bin/env python3

import argparse
import asyncio
import logging
import sys
import traceback

logger = logging.getLogger('lrc')


class UnrecognizedInstruction(Exception):
    pass


class Terminate(Exception):
    pass


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


class TerminalStdout(object):
    def __init__(self, memory):
        self.memory = memory
        self.loop = asyncio.get_event_loop()
        self.buf = list()

    @asyncio.coroutine
    def listen(self):
        try:
            val = self.memory.read(0)
            if val != 0:
                self.buf.append(val)
                self.memory.write(0, 0)
                self.loop.call_soon(self.flush)

            self.loop.create_task(self.listen())

        finally:
            self.flush()

    def flush(self):
        sys.stdout.write(''.join(map(chr, self.buf)))
        self.buf = list()


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
        self.log = logging.getLogger('lrc.interpreter')
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
        self.log.info('run start')
        loop = asyncio.get_event_loop()

        @asyncio.coroutine
        def shutdown():
            for task in asyncio.Task.all_tasks():
                task.cancel()

            loop.call_soon(loop.stop)

        @asyncio.coroutine
        def tick():
            self.log.debug('tick')

            try:
                data = memory.read(memory.ptr)
                if data == 0:
                    raise Terminate()

                opcode, lo, hi = self.interpret(data)
                self.opcodes[opcode](memory, lo, hi)

                memory.ptr += 1

                loop.create_task(tick())

            except Terminate:
                loop.create_task(shutdown())

            except Exception:
                traceback.print_exc()
                loop.create_task(shutdown())

        loop.create_task(tick())
        loop.run_forever()

        self.log.info('run stop')

    def interpret(self, data):
        mask_ins = 2**4 - 1
        mask_low = 2**16 - 1

        # retrieve the opcode
        opcode = data & mask_ins
        data = data >> 4

        # retrieve the lo and hi data
        lo = data & mask_low
        hi = (data >> 16) & mask_low

        return opcode, lo, hi

    def _load(self, memory, lo, hi):
        self.log.debug("LDA {}".format(lo))
        memory.write_eax(lo)

    def _increment(self, memory, lo, hi):
        self.log.debug("INC {}".format(lo))
        val = memory.read(lo)
        memory.write(lo, val + 1)

    def _decrement(self, memory, lo, hi):
        self.log.debug("DEC {}".format(lo))
        val = memory.read(lo)
        memory.write(lo, val - 1)

    def _store(self, memory, lo, hi):
        self.log.debug("STA {}".format(lo))
        val = memory.read_eax()
        memory.write(lo, val)

    def _addition(self, memory, lo, hi):
        self.log.debug("ADD {} {}".format(lo, hi))
        val = (memory.read(lo) + memory.read(hi)) % 2**16
        memory.write(lo, val)

    def _subtraction(self, memory, lo, hi):
        self.log.debug("SUB {} {}".format(lo, hi))
        val = (memory.read(lo) - hi) % 2**16
        memory.write(lo, val)

    def _jump(self, memory, lo, hi):
        self.log.debug("JMP {}".format(lo))
        memory.ptr = lo - 1

    def _move(self, memory, lo, hi):
        self.log.debug("MOV {} {}".format(lo, hi))
        val = memory.read(hi)
        memory.write(lo, val)


class Compiler(object):
    def compile(self, program):
        log = logging.getLogger('lrc.compiler')

        instructions = list()
        for line in program.splitlines():
            if line and not line.startswith('#'):
                mneumonic, data = line.split(' ', 1)

                if mneumonic == 'LDA':
                    value = int(data)
                    instructions.append(Load(value))
                    log.debug('LDA {}'.format(value))
                    continue

                if mneumonic == 'STA':
                    value = int(data)
                    instructions.append(Store(value))
                    log.debug('STA {}'.format(value))
                    continue

                if mneumonic == "INC":
                    value = int(data)
                    instructions.append(Increment(value))
                    log.debug('INC {}'.format(value))
                    continue

                if mneumonic == "DEC":
                    value = int(data)
                    instructions.append(Decrement(value))
                    log.debug('DEC {}'.format(value))
                    continue

                if mneumonic == "ADD":
                    value1, value2 = data.split()
                    value1 = int(value1)
                    value2 = int(value2)
                    instructions.append(Addition(value1, value2))
                    log.debug('ADD {} {}'.format(value1, value2))
                    continue

                if mneumonic == "SUB":
                    value1, value2 = data.split()
                    value1 = int(value1)
                    value2 = int(value2)
                    instructions.append(Subtraction(value1, value2))
                    log.debug('SUB {} {}'.format(value1, value2))
                    continue

                if mneumonic == "JMP":
                    value = int(data)
                    instructions.append(Jump(value))
                    log.debug('JMP {}'.format(value))
                    continue

                if mneumonic == "MOV":
                    value1, value2 = data.split()
                    value1 = int(value1)
                    value2 = int(value2)
                    instructions.append(Move(value1, value2))
                    log.debug('MOV {} {}'.format(value1, value2))
                    continue

                raise UnrecognizedInstruction()

        return instructions


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", "-f")
    parser.add_argument("--dump", "-d", action='store_true')
    parser.add_argument("--log-level", "-l", choices=('debug', 'info', 'error'), default='error')

    args = parser.parse_args(argv)

    logging_levels = {
            'debug': logging.DEBUG,
            'error': logging.ERROR,
            'info': logging.INFO,
            }

    logging.getLogger('lrc').setLevel(logging_levels[args.log_level])

    program = open(args.file).read()

    memory = Memory()

    stdout = TerminalStdout(memory)
    loop = asyncio.get_event_loop()
    loop.create_task(stdout.listen())

    compiler = Compiler()
    instructions = compiler.compile(program)

    for index, instruction in zip(range(len(instructions)), instructions):
        memory.write(Memory.ADDR_PRG + index, instruction.value)

    interpreter = Interpreter()
    interpreter.run(memory)

    if args.dump:
        print()
        for addr in memory:
            print('>', addr)

if __name__ == "__main__":
    logging.basicConfig()
    main()
