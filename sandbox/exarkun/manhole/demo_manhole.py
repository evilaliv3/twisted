
from twisted.application import service
application = service.Application("Interactive Python Interpreter")

from demolib import makeService
from manhole import ColoredManhole

makeService({'protocolFactory': ColoredManhole,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)