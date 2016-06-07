import asyncio
import logging
import traceback

from . import core


logger = logging.getLogger(__name__)


class UnrecognizedInstruction(Exception):
    pass


class SegmentationFault(Exception):
    pass


class Interpreter(object):
    def __init__(self):
        self.opcodes = {op.OPCODE: op for op in (
            core.Load,
            core.Increment,
            core.Store,
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

    def run(self, memory):
        logger.info('run start')
        loop = asyncio.get_event_loop()

        @asyncio.coroutine
        def shutdown():
            for task in asyncio.Task.all_tasks():
                task.cancel()

            loop.call_soon(loop.stop)

        @asyncio.coroutine
        def tick():
            try:
                opcode = self.interpret(memory.read(memory.ptr))
                logger.debug("@{}: {} {} {}".format(
                    memory.ptr,
                    opcode.mneumonic,
                    opcode.lo,
                    opcode.hi,
                    ))

                opcode.execute(memory)

                memory.ptr += 1

                if memory.ptr > len(memory):
                    raise SegmentationFault()

                loop.create_task(tick())

            except core.Terminate:
                loop.create_task(shutdown())

            except Exception:
                traceback.print_exc()
                loop.create_task(shutdown())

        loop.create_task(tick())
        loop.run_forever()

        logger.info('run stop')

    def interpret(self, data):
        mask_in = 2**32 - 2**28
        mask_lo = 2**28 - 2**14
        mask_hi = 2**14 - 2**0

        # retrieve the lo and hi data
        lo = core.Operand((data & mask_lo) >> 14)
        hi = core.Operand(data & mask_hi)

        # retrieve the opcode
        ins = (data & mask_in) >> 28
        opcode = self.opcodes[ins](lo=lo, hi=hi)

        return opcode
