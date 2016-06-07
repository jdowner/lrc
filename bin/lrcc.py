#!/usr/bin/env python3

import argparse
import asyncio
import logging
import logging.config
import os
import sys

import lrc.compiler
import lrc.core
import lrc.device
import lrc.interpreter

logger = logging.getLogger('lrc')


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

    memory = lrc.core.Memory()

    compiler = lrc.compiler.Compiler()
    instructions = compiler.compile(program)
    memory.load_program(instructions)

    stdout = lrc.device.TerminalStdout(memory)
    loop = asyncio.get_event_loop()
    loop.create_task(stdout.listen())

    interpreter = lrc.interpreter.Interpreter()
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
