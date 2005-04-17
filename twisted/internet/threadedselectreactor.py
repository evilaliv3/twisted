# -*- test-case-name: twisted.test.test_internet -*-
# $Id: default.py,v 1.90 2004/01/06 22:35:22 warner Exp $
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import generators

"""Threaded select reactor

API Stability: unstable

Maintainer: U{Bob Ippolito<mailto:bob@redivi.com>}
"""

from threading import Thread
from Queue import Queue, Empty
from time import sleep
import sys

from zope.interface import implements

from twisted.internet.interfaces import IReactorFDSet
from twisted.internet import error
from twisted.internet import posixbase
from twisted.python import log, components
from twisted.persisted import styles
from twisted.python.runtime import platformType

import select
from errno import EINTR, EBADF

def win32select(r, w, e, timeout=None):
    """Win32 select wrapper."""
    if not (r or w):
        # windows select() exits immediately when no sockets
        if timeout is None:
            timeout = 0.01
        else:
            timeout = min(timeout, 0.001)
        sleep(timeout)
        return [], [], []
    # windows doesn't process 'signals' inside select(), so we set a max
    # time or ctrl-c will never be recognized
    if timeout is None or timeout > 0.5:
        timeout = 0.5
    r, w, e = select.select(r, w, w, timeout)
    return r, w + e, []

if platformType == "win32":
    _select = win32select
else:
    _select = select.select

# Exceptions that doSelect might return frequently
_NO_FILENO = error.ConnectionFdescWentAway('Handler has no fileno method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')

def dictRemove(dct, value):
    try:
        del dct[value]
    except KeyError:
        pass

def raiseException(e):
    raise e

class ThreadedSelectReactor(posixbase.PosixReactorBase):
    """A threaded select() based reactor - runs on all POSIX platforms and on
    Win32.
    """
    implements(IReactorFDSet)

    def __init__(self):
        self.usingThreads = 1
        self.reads = {}
        self.writes = {}
        self.toThreadQueue = Queue()
        self.toMainThread = Queue(1)
        self.workerThread = None
        self.mainWaker = None
        posixbase.PosixReactorBase.__init__(self)
        self.addSystemEventTrigger('after', 'shutdown', self._mainLoopShutdown)

    def wakeUp(self):
        # we want to wake up from any thread
        self.waker.wakeUp()

    def callLater(self, *args, **kw):
        tple = posixbase.PosixReactorBase.callLater(self, *args, **kw)
        self.wakeUp()
        return tple
    
    def _sendToMain(self, msg, *args):
        #print >>sys.stderr, 'sendToMain', msg, args
        self.toMainThread.put((msg, args))
        if self.mainWaker is not None:
            self.mainWaker()

    def _sendToThread(self, fn, *args):
        #print >>sys.stderr, 'sendToThread', fn, args
        self.toThreadQueue.put((fn, args))
    
    def _preenDescriptorsInThread(self):
        log.msg("Malformed file descriptor found.  Preening lists.")
        readers = self.reads.keys()
        writers = self.writes.keys()
        self.reads.clear()
        self.writes.clear()
        for selDict, selList in ((self.reads, readers), (self.writes, writers)):
            for selectable in selList:
                try:
                    select.select([selectable], [selectable], [selectable], 0)
                except:
                    log.msg("bad descriptor %s" % selectable)
                else:
                    selDict[selectable] = 1

    def _workerInThread(self):
        try:
            while 1:
                fn, args = self.toThreadQueue.get()
                #print >>sys.stderr, "worker got", fn, args
                fn(*args)
        except SystemExit:
            pass
        except:
            self._sendToMain('Exception', sys.exc_info())
        #print >>sys.stderr, "worker finished"
    
    def _doSelectInThread(self, timeout):
        """Run one iteration of the I/O monitor loop.

        This will run all selectables who had input or output readiness
        waiting for them.
        """
        reads = self.reads
        writes = self.writes
        while 1:
            try:
                r, w, ignored = _select(reads.keys(),
                                        writes.keys(),
                                        [], timeout)
                break
            except ValueError, ve:
                # Possibly a file descriptor has gone negative?
                log.err()
                self._preenDescriptorsInThread()
            except TypeError, te:
                # Something *totally* invalid (object w/o fileno, non-integral
                # result) was passed
                log.err()
                self._preenDescriptorsInThread()
            except (select.error, IOError), se:
                # select(2) encountered an error
                if se.args[0] in (0, 2):
                    # windows does this if it got an empty list
                    if (not reads) and (not writes):
                        return
                    else:
                        raise
                elif se.args[0] == EINTR:
                    return
                elif se.args[0] == EBADF:
                    self._preenDescriptorsInThread()
                else:
                    # OK, I really don't know what's going on.  Blow up.
                    raise
        self._sendToMain('Notify', r, w)
        
    def _process_Notify(self, r, w):
        #print >>sys.stderr, "_process_Notify"
        reads = self.reads
        writes = self.writes
    
        _drdw = self._doReadOrWrite
        _logrun = log.callWithLogger
        for selectables, method, dct in ((r, "doRead", reads), (w, "doWrite", writes)):
            for selectable in selectables:
                # if this was disconnected in another thread, kill it.
                if selectable not in dct:
                    continue
                # This for pausing input when we're not ready for more.
                _logrun(selectable, _drdw, selectable, method, dct)
        #print >>sys.stderr, "done _process_Notify"

    def _process_Exception(self, exc_info):
        raise exc_info[1]

    _doIterationInThread = _doSelectInThread

    def ensureWorkerThread(self):
        if self.workerThread is None or not self.workerThread.isAlive():
            self.workerThread = Thread(target=self._workerInThread)
            self.workerThread.setDaemon(True)
            self.workerThread.start()
    
    def doThreadIteration(self, timeout):
        self._sendToThread(self._doIterationInThread, timeout)
        self.ensureWorkerThread()
        #print >>sys.stderr, 'getting...'
        msg, args = self.toMainThread.get()
        #print >>sys.stderr, 'got', msg, args
        getattr(self, '_process_' + msg)(*args)
    
    doIteration = doThreadIteration

    def mainLoopBegin(self):
        if self.running:
            self.runUntilCurrent()

    def _interleave(self):
        while self.running:
            #print >>sys.stderr, "runUntilCurrent"
            self.runUntilCurrent()
            t2 = self.timeout()
            t = self.running and t2
            self._sendToThread(self._doIterationInThread, t)
            #print >>sys.stderr, "yielding"
            yield None
            #print >>sys.stderr, "fetching"
            msg, args = self.toMainThread.get_nowait()
            getattr(self, '_process_' + msg)(*args)

    def interleave(self, waker, *args, **kw):
        """
        waker(func) is a callable that will be called from
        some random thread.  Its job is to call func from
        the same thread that called this method.

        You should use this like a ninja master to integrate
        with foreign event loops.
        """
        self.startRunning(*args, **kw)
        loop = self._interleave()
        def mainWaker(waker=waker, loop=loop):
            #print >>sys.stderr, "mainWaker()"
            waker(loop.next)
        self.mainWaker = mainWaker
        loop.next()
        self.ensureWorkerThread()
    
    def _mainLoopShutdown(self):
        self.mainWaker = None
        if self.workerThread is not None:
            #print >>sys.stderr, 'getting...'
            self._sendToThread(raiseException, SystemExit)
            self.wakeUp()
            try:
                while 1:
                    msg, args = self.toMainThread.get_nowait()
                    #print >>sys.stderr, "ignored:", (msg, args)
            except Empty:
                pass
            self.workerThread.join()
            self.workerThread = None
        try:
            while 1:
                fn, args = self.toThreadQueue.get_nowait()
                if fn is self._doIterationInThread:
                    log.msg('Iteration is still in the thread queue!')
                elif fn is raiseException and args[0] is SystemExit:
                    pass
                else:
                    fn(*args)
        except Empty:
            pass

    def _doReadOrWrite(self, selectable, method, dict):
        try:
            why = getattr(selectable, method)()
            handfn = getattr(selectable, 'fileno', None)
            if not handfn:
                why = _NO_FILENO
            elif handfn() == -1:
                why = _NO_FILEDESC
        except:
            why = sys.exc_info()[1]
            log.err()
        if why:
            self._disconnectSelectable(selectable, why, method == "doRead")
    
    def addReader(self, reader):
        """Add a FileDescriptor for notification of data available to read.
        """
        self._sendToThread(self.reads.__setitem__, reader, 1)
        self.wakeUp()

    def addWriter(self, writer):
        """Add a FileDescriptor for notification of data available to write.
        """
        self._sendToThread(self.writes.__setitem__, writer, 1)
        self.wakeUp()

    def removeReader(self, reader):
        """Remove a Selectable for notification of data available to read.
        """
        self._sendToThread(dictRemove, self.reads, reader)

    def removeWriter(self, writer):
        """Remove a Selectable for notification of data available to write.
        """
        self._sendToThread(dictRemove, self.writes, writer)

    def removeAll(self):
        return self._removeAll(self.reads, self.writes)
        
    
components.backwardsCompatImplements(ThreadedSelectReactor)


def install():
    """Configure the twisted mainloop to be run using the select() reactor.
    """
    reactor = ThreadedSelectReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)

__all__ = ['install']
