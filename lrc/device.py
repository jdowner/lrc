import asyncio
import logging
import sys


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

