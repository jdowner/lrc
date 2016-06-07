#!/usr/bin/env python3

import asyncio
import logging
import logging.config
import re
import sys

from . import core

logger = logging.getLogger(__name__)


class UnrecognizedInstruction(Exception):
    pass


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


class Compiler(object):
    def __init__(self):
        self._opcodes = {op.MNEUMONIC: op for op in (
            core.Load,
            core.Store,
            core.Increment,
            core.Decrement,
            core.Addition,
            core.Subtraction,
            core.Jump,
            core.Move,
            core.Compare,
            core.BranchAbove,
            core.BranchBelow,
            core.Null,
            core.Halt,
            )}

        self._label_pattern = re.compile('^[a-zA-Z][-_0-9a-zA-Z]*:')

    def compile(self, program):
        # Remove non-functional lines from the program
        lines = self.prepare(program)

        # Find any labels and create a map of their addresses
        labels = self.find_labels(lines)

        # Compile the instructions
        instructions = list()
        for line in lines:
            if self.is_label(line):
                instructions.append(core.Null(lo=0, hi=0))
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
                labels[label] = index + core.Memory.ADDR_PRG

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
        arguments = line[3:].strip()

        lo = 0
        hi = 0

        if arguments:
            parts = arguments.split(",")

            if len(parts) >= 1:
                lo = eval(parts[0], None, labels)

            if len(parts) == 2:
                hi = eval(parts[1], None, labels)

        opcode = self._opcodes[mneumonic](lo=lo, hi=hi)

        return opcode
