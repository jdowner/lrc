#!/usr/bin/env python3

import argparse
import asyncio
import logging
import logging.config
import os
import re
import sys
import traceback

logger = logging.getLogger('lrc')


class UnrecognizedInstruction(Exception):
    pass


class Terminate(Exception):
    pass


class SegmentationFault(Exception):
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
        return self.read(Memory.ADDR_REG)

    def write_eax(self, value):
        self.write(Memory.ADDR_REG, value)

    @property
    def flag_cmp(self):
        return self.read(Memory.ADDR_FLG)

    @flag_cmp.setter
    def flag_cmp(self, val):
        self.write(Memory.ADDR_FLG, val)


class TerminalStdout(object):
    def __init__(self, memory):
        self.memory = memory
        self.log = logging.getLogger('lrc.terminal')
        self.loop = asyncio.get_event_loop()
        self.buf = list()

    @asyncio.coroutine
    def listen(self):
        try:
            val = self.memory.read(0)
            if val != 0:
                self.log.debug('read {}'.format(val))
                self.buf.append(val)
                self.memory.write(0, 0)
                self.loop.call_soon(self.flush)

            self.loop.create_task(self.listen())

        finally:
            self.flush()

    def flush(self):
        self.log.debug("write {}".format(self.buf))
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
    def __init__(self, data):
        super(NullaryOp, self).__init__()

    @property
    def value(self):
        return self.opcode


class UnaryOp(BaseOp):
    def __init__(self, data):
        mask = 2**16 - 1
        data = int(data)
        lo = mask & data
        super(UnaryOp, self).__init__(lo=lo)

    @property
    def value(self):
        return self.opcode + (self.lo << 4)


class BinaryOp(BaseOp):
    def __init__(self, data):
        mask = 2**16 - 1
        lo, hi = data
        lo = mask & int(lo)
        hi = mask & int(hi)
        super(BinaryOp, self).__init__(lo=lo, hi=hi)

    @property
    def value(self):
        return self.opcode + (self.lo << 4) + (self.hi << 20)


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


class Interpreter(object):
    class Data(object):
        MASK_VAL = (2 << 12) - 1
        MASK_REF = 2 << 12

        def __init__(self, data):
            self.data = data

        def __repr__(self):
            return repr(self.data)

        @property
        def value(self):
            return self.data & Interpreter.Data.MASK_VAL

        @property
        def is_ref(self):
            return self.data & Interpreter.Data.MASK_REF


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
                Compare.OPCODE:     self._compare,
                BranchAbove.OPCODE: self._branch_above,
                BranchBelow.OPCODE: self._branch_below,
                Null.OPCODE:        self._null,
                Halt.OPCODE:        self._halt,
                }

        self.mneumonics = {ins.OPCODE: ins.MNEUMONIC for ins in (
            Load,
            Increment,
            Store,
            Decrement,
            Addition,
            Subtraction,
            Jump,
            Move,
            Compare,
            BranchAbove,
            BranchBelow,
            Null,
            Halt,
            )}

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
            try:
                opcode, lo, hi = self.interpret(memory.read(memory.ptr))
                self.log.debug("@{}: {} {} {}".format(
                    memory.ptr,
                    self.mneumonics[opcode],
                    lo,
                    hi,
                    ))

                self.opcodes[opcode](memory, lo, hi)

                memory.ptr += 1

                if memory.ptr > len(memory):
                    raise SegmentationFault()

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
        memory.write_eax(lo)

    def _increment(self, memory, lo, hi):
        val = memory.read(lo)
        memory.write(lo, val + 1)

    def _decrement(self, memory, lo, hi):
        val = memory.read(lo)
        memory.write(lo, val - 1)

    def _store(self, memory, lo, hi):
        val = memory.read_eax()
        memory.write(lo, val)

    def _addition(self, memory, lo, hi):
        val = (memory.read(lo) + memory.read(hi)) % 2**16
        memory.write(lo, val)

    def _subtraction(self, memory, lo, hi):
        val = (memory.read(lo) - hi) % 2**16
        memory.write(lo, val)

    def _jump(self, memory, lo, hi):
        memory.ptr = lo - 1

    def _move(self, memory, lo, hi):
        val = memory.read(hi)
        memory.write(lo, val)

    def _compare(self, memory, lo, hi):
        vlo = memory.read(lo)
        vhi = memory.read(hi)
        memory.flag_cmp = 1 if vlo < vhi else 0

    def _branch_above(self, memory, lo, hi):
        if memory.flag_cmp == 0:
            memory.ptr = lo - 1

    def _branch_below(self, memory, lo, hi):
        if memory.flag_cmp == 1:
            memory.ptr = lo - 1

    def _null(self, memory, lo, hi):
        pass

    def _halt(self, memory, lo, hi):
        raise Terminate()


class Compiler(object):
    def __init__(self):
        self._opcodes = {
                'LDA': Load,
                'STA': Store,
                'INC': Increment,
                'DEC': Decrement,
                'ADD': Addition,
                'SUB': Subtraction,
                'JMP': Jump,
                'MOV': Move,
                'CMP': Compare,
                'BRA': BranchAbove,
                'BRB': BranchBelow,
                'NUL': Null,
                'HLT': Halt,
                }
        self._label_pattern = re.compile('^[a-zA-Z][-_0-9a-zA-Z]*:')
        self._log = logging.getLogger('lrc.compiler')

    def compile(self, program):
        # Remove non-functional lines from the program
        lines = self.prepare(program)

        # Find any labels and create a map of their addresses
        labels = self.find_labels(lines)

        # Compile the instructions
        instructions = list()
        for line in lines:
            if self.is_label(line):
                instructions.append(Null(None))
                continue

            if self.is_opcode(line):
                opcode = self.parse_opcode(labels, line)
                instructions.append(opcode)
                continue

            raise UnrecognizedInstruction(line)

        return instructions

    def prepare(self, program):
        lines = program.splitlines()
        lines = [line.strip() for line in lines if not self.is_comment(line)]
        return lines

    def find_labels(self, lines):
        labels = {}
        for index, line in zip(range(len(lines)), lines):
            if self.is_label(line):
                label = self.parse_label(line)
                assert label not in labels
                labels[label] = index + Memory.ADDR_PRG

        return labels

    def is_comment(self, line):
        return not line or line.startswith('#')

    def is_label(self, line):
        return self._label_pattern.match(line)

    def is_opcode(self, line):
        return line[:3] in self._opcodes and (not line[3:] or line[3] == ' ')

    def parse_label(self, line):
        return line[:line.find(':')]

    def parse_opcode(self, labels, line):
        mneumonic = line[:3]

        data = line[3:].strip()
        if data:
            data = eval(data, None, labels)

        opcode = self._opcodes[mneumonic](data)
        self._log.debug('{} {}'.format(mneumonic, data))

        return opcode


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", "-d", action='store_true')
    parser.add_argument("--log-level", "-l", choices=('debug', 'info', 'error'), default='error')
    parser.add_argument("file", nargs=argparse.REMAINDER)

    args = parser.parse_args(argv)

    logging_levels = {
            'debug': logging.DEBUG,
            'error': logging.ERROR,
            'info': logging.INFO,
            }

    logging.getLogger('lrc').setLevel(logging_levels[args.log_level])

    program = open(args.file[0]).read()

    memory = Memory()

    compiler = Compiler()
    instructions = compiler.compile(program)

    for index, instruction in zip(range(len(instructions)), instructions):
        memory.write(Memory.ADDR_PRG + index, instruction.value)

    stdout = TerminalStdout(memory)
    loop = asyncio.get_event_loop()
    loop.create_task(stdout.listen())

    interpreter = Interpreter()
    interpreter.run(memory)

    if args.dump:
        print()
        for index, addr in zip(range(len(memory)), memory):
            mask = 2**16 - 1
            lo = mask & addr
            hi = (addr >> 16) & mask
            print('[{0:#06x}] {1:04x} {2:04x}'.format(index, hi, lo))


if __name__ == "__main__":
    cfg = os.path.expandvars("${XDG_CONFIG_HOME}/lrc/logging.cfg")
    if os.path.exists(os.path.exists(cfg)):
        logging.config.fileConfig(cfg)

    else:
        logging.basicConfig()

    main()
