# -*- test-case-name: twisted.test.test_postfix -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2003 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

"""Postfix mail transport agent related protocols."""

# Twisted imports
from twisted.protocols import basic
from twisted.protocols import policies
from twisted.internet import protocol
import UserDict
import urllib

# urllib's quote functions just happen to match
# the postfix semantics.

def quote(s):
    return urllib.quote(s)

def unquote(s):
    return urllib.unquote(s)

class PostfixTCPMapServer(basic.LineReceiver, policies.TimeoutMixin):
    """Postfix mail transport agent TCP map protocol implementation.

    Receive requests for data matching given key via lineReceived,
    asks it's factory for the data with dictionary-style access, and
    returns the data to the requester.

    You can use postfix's postmap to test the map service::

    /usr/sbin/postmap -q KEY tcp:localhost:4242

    """

    timeout = 600
    delimiter = '\n'

    def connectionMade(self):
        self.setTimeout(self.timeout)

    def sendCode(self, code, message=''):
        "Send an SMTP-like code with a message."
        self.sendLine('%3.3d %s' % (code, message or ''))

    def lineReceived(self, line):
        self.resetTimeout()
        splitted = line.split(None)
        request = splitted[0]
        params = splitted[1:]
        try:
            f = getattr(self, 'do_' + request)
        except AttributeError:
            self.sendCode(400, 'unknown command')
        else:
            numOfParams = f.im_func.func_code.co_argcount - 1 # don't count self
            if len(params) != numOfParams:
                self.sendCode(400, 'Command %r takes %d parameters.' % (request, numOfParams))
            else:
                f(*params)

    def do_get(self, key):
        try:
            value = self.factory[key]
        except KeyError, e:
            self.sendCode(500)
        else:
            self.sendCode(200, quote(value))

    def do_put(self, key, value):
        self.sendCode(500, 'put is not implemented yet.')


class PostfixTCPMapDictServerFactory(protocol.ServerFactory,
                                     UserDict.UserDict):
    """An in-memory dictionary factory for PostfixTCPMapServer."""

    protocol = PostfixTCPMapServer

if __name__ == '__main__':
    """Test app for PostfixTCPMapServer. Call with parameters
    KEY1=VAL1 KEY2=VAL2 ..."""
    from twisted.internet import reactor
    from twisted.python import log
    import sys
    log.startLogging(sys.stdout)
    d = {}
    for arg in sys.argv[1:]:
        try:
            k,v = arg.split('=', 1)
        except ValueError:
            k = arg
            v = ''
        d[k]=v
    f=PostfixTCPMapDictServerFactory(d)
    port = reactor.listenTCP(4242, f, interface='127.0.0.1')
    reactor.run()
