#! /usr/bin/python

from twisted.spread import pb
import twisted.internet.app

class MyError(pb.Error):
    """This is an Expected Exception. Something bad happened."""
    pass

class MyError2(Exception):
    """This is an Unexpected Exception. Something really bad happened."""
    pass

class One(pb.Root):
    def remote_broken(self):
        msg = "fall down go boom"
        print "raising a MyError exception with data '%s'" % msg
        raise MyError(msg)
    def remote_broken2(self):
        msg = "hadda owie"
        print "raising a MyError2 exception with data '%s'" % msg
        raise MyError2(msg)

def main():
    app = twisted.internet.app.Application("exc_server")
    app.listenTCP(8800, pb.BrokerFactory(One()))
    app.run()

if __name__ == '__main__':
    main()
