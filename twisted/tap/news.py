# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
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
from twisted.news import news, database
from twisted.protocols import nntp
from twisted.python import usage

class Options(usage.Options):
    synopsis = "Usage: mktap nntp [options]"
    
    optParameters = [
        ["port", "p", "119", "Listen port"]
    ]

    def __init__(self):
        usage.Options.__init__(self)

    def opt_port(self, port):
        self.port = port

def updateApplication(app, config):
    app.listenTCP(
        int(config.opts['port']),
        news.createNNTPFactory(nntp.NNTPServer, database.PickleStorage)
    )
