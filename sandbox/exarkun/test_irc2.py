# -*- coding: Latin-1 -*-

from irc2 import ActionInProgress, NoSuchChannel, AdvancedClient

from twisted.python import log
from twisted.internet import defer
from twisted.internet import protocol
from twisted.trial import unittest
from twisted.test.proto_helpers import LineSendingProtocol
from twisted.protocols import loopback

class AdvancedTestClient(AdvancedClient):
    nickname = "user"

    def __init__(self):
        self.onC = defer.Deferred()
        AdvancedClient.__init__(self)

    def connectionMade(self):
        # Intentional don't call the superclass method
        self.onC.callback(self)
        

class SimpleActionTestCase(unittest.TestCase):
    success = False
    failure = None

    def succeed(self, proto):
        self.success = True
        proto.transport.loseConnection()
    
    def fail(self, failure, proto):
        self.failure = failure
        proto.transport.loseConnection()

    def testJoin(self):
        server = LineSendingProtocol([
            ":user!ident@hostmask JOIN :#channel",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.join("#channel")
            ).addCallback(self.succeed
            ).addErrback(self.fail
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testIllegalJoin(self):
        server = LineSendingProtocol([
            ":host.domain.tld 403 user #nonexist :That channel doesn't exist",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.join("#nonexist")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(self.success)
        self.failure.trap(NoSuchChannel)

    def testPart(self):
        server = LineSendingProtocol([
            ":user!ident@hostmask PART #channel :Reason"
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.part("#channel")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testIllegalPart(self):
        server = LineSendingProtocol([
            ":host.domain.tld 403 user #nonexist :That channel doesn't exist",
        ], False)
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.part("#nonexist")
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(self.success)
        self.failure.trap(NoSuchChannel)

    def testQuit(self):
        server = protocol.Protocol()
        server.dataReceived = lambda data: server.transport.loseConnection()
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: p.quit()
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failUnless(self.success)
    
    def testIllegalQuit(self):
        server = protocol.Protocol()
        server.dataReceived = lambda data: server.transport.loseConnection()
        client = AdvancedTestClient()
        client.onC.addCallback(lambda p: (p.quit(), p.quit())
            ).addCallback(self.succeed
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.failIf(self.success)
        self.failure.trap(ActionInProgress)

    def testNames(self):
        server = LineSendingProtocol([
            ":server 353 user = #channel :user another1 another2 another3",
            ":server 353 user = #channel :another4 another5",
            ":server 366 user #channel :End of /NAMES list."
        ], False)
        client = AdvancedTestClient()
        names = {}
        client.onC.addCallback(lambda p: p.names("#channel")
            ).addCallback(names.update
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(names, {'#channel': [
            "user", "another1", "another2", "another3", "another4",
            "another5"
        ]})

    def testWho(self):
        server = LineSendingProtocol([
            ":server 352 user pattern jjs9GN0GAm hostmask3 servername1 user1 H :0 fullname2",
            ":server 352 user pattern 15j7VkjDbD hostmask1 servername2 user2 H :2 fullname3",
            ":server 352 user pattern 4X7zQjVK7h hostmask2 servername3 user3 H :3 fullname1",
            ":server 315 user pattern :End of /WHO list.",
        ])
        client = AdvancedTestClient()
        who = []
        client.onC.addCallback(lambda p: p.who("pattern")
            ).addCallback(who.extend
            ).addCallback(lambda _: client.transport.loseConnection()
            ).addErrback(self.fail, client
            )
        loopback.loopback(server, client)
        self.assertEquals(who, [
            ("jjs9GN0GAm", "hostmask3", "servername1", "user1", "H", 0, "fullname2"),
            ("15j7VkjDbD", "hostmask1", "servername2", "user2", "H", 2, "fullname3"),
            ("4X7zQjVK7h", "hostmask2", "servername3", "user3", "H", 3, "fullname1"),
        ])
