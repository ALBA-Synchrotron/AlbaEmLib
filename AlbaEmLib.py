

import sys
#import pyIcePAP
import time
import PyTango
#from pylab import *
import array
from scipy.stats import *
import socket
import datetime

from threading import Lock, Thread

class ReconnectThread(Thread):
    def __init__(self, albaEm, sleepTime):
        Thread.__init__(self)
        self.albaEm = albaEm 
        self.sleepTime = sleepTime

    def run(self):
        while True:
            if not self.albaEm.connected:
                self.albaEm.tryToConnect()
            time.sleep(self.sleepTime)

class albaem():
    ''' The configuration of the serial line is: 8bits + 1 stopbit, bdr: 9600, terminator:none'''
    ''' The cable is crossed'''
    myalbaemds = None
    DEBUG = False

    def __init__(self, host, port=7):
        self.connected = True #Todo: This variable is not needed anymore and the ReconnectThread neither.
        self.DEBUG = False
        self.host = host
        self.port = port
        self.lock = Lock()
        
#        self.reconnect_thread = ReconnectThread(self, 2)
#        self.reconnect_thread.setDaemon(True)
#        self.reconnect_thread.start()
        
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)

    def savechain(self, savedchain):
        self.savedchain = savedchain+'\x00'

    def ask2(self, cmd, size=8192):
        print "ask: %s"%self.savedchain
        return self.savedchain

    def ask(self, cmd, size=8192):
        try:
            self.lock.acquire()
            if self.connected:
                self.sock.sendto(cmd, (self.host, self.port))
                data = self.sock.recv(size)
            else:
                raise Exception('Device not found!')
            if self.DEBUG:
                print 'AlbaEM DEBUG: query:',cmd,'\t','answer length:', len(data), '\t', 'answer:#%s#'%(data)
            return data
         
        except socket.timeout, timeout:
            try:
                if self.connected:
                    self.sock.sendto(cmd, (self.host, self.port))
                    data = self.sock.recv(size)
                else:
                    raise Exception('Device not found!')
                return data
            except Exception, e:
                print 'Timeout Error'
                return 'Socket timeout'
        except socket.error, error:
            print 'Socket Error'
            return 'Socket Error'
        except Exception, e:
            print 'Unknown Error'
            return 'Unknown Exception'
        finally:
            self.lock.release()

    def extractMultichannel(self, chain, initialpos):
        answersplit = chain.strip('\x00').split(' ')
        if answersplit[0] == '?MEAS':
            status = answersplit[len(answersplit) - 1]
            parameters = answersplit[initialpos:len(answersplit)-1]
        else:
            parameters = answersplit[initialpos:len(answersplit)]
        couples = []
        if len(parameters)%2 != 0:
            raise Exception('extractMultichannel: Wrong number of parameters')
        for i in range(0, len(parameters)/2):
            if parameters[i*2] in ['1', '2', '3', '4']:
                couples.append([parameters[i*2], parameters[i*2 + 1]])
            else: 
                raise Exception('extractMultichannel: Wrong channel')
        if self.DEBUG:
            print "extractMultichannel:%s"%(couples)
        if answersplit[0] == '?MEAS':
            return couples, status
        else: 
            return couples

    def extractSimple(self, chain):
        return chain.strip('\x00').split(' ')[1]


    def getRanges(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?RANGE %s'%channelchain
            answer = self.ask(command)
            if self.DEBUG:
                print "getRanges: SEND: %s\t RCVD: %s"%(command, answer)
            ranges = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getRanges: %s"%(e)
            return None
        if self.DEBUG:
            print "getRanges: SEND: %s\t RCVD: %s"%(command, answer)
            print "getRanges: %s"%(ranges)
        return ranges

    def getRangesAll(self):
        self.getRanges(['1', '2', '3', '4'])

    def _setRanges(self, ranges):
        channelchain = ''
        '''
        try: 
            for couple in ranges:
                channelchain = '%s %s '%(couple[0], couple[1])
                command = 'RANGE %s'%(channelchain)
                answer = self.ask(command)
        '''
        for couple in ranges:
            channelchain = '%s %s %s'%(channelchain, couple[0], couple[1])
        try: 
            command = 'RANGE %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'RANGE ACK\x00':
                raise Exception('setRanges: Wrong acknowledge')
        except Exception, e:
            print "setRanges: %s"%(e)
        if self.DEBUG:
            print "setRanges: SEND: %s\t RCVD: %s"%(command, answer)

    def setRanges(self, ranges):
        self.StopAdc()
        self._setRanges(ranges)
        self.StartAdc()

    def setRangesAll(self, range):
        self.StopAdc()
        self.setRanges([['1', range], ['2', range], ['3', range], ['4', range]])
        self.StartAdc()

    def getEnables(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?ENABLE %s'%channelchain
            answer = self.ask(command)
            enables = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getEnables: %s"%(e)
            return None
        if self.DEBUG:
            print "getEnables: SEND: %s\t RCVD: %s"%(command, answer)
            print "getEnables: %s"%(enables)
        return enables

    def getEnablesAll(self):
        self.getEnables(['1', '2', '3', '4'])

    def _setEnables(self, enables):
        channelchain = ''
        for couple in enables:
            channelchain = '%s %s %s '%(channelchain, couple[0], couple[1])
        try: 
            command = 'ENABLE %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'ENABLE ACK\x00':
                raise Exception('setEnables: Wrong acknowledge')
        except Exception, e:
            print "setEnables: %s"%(e)
        if self.DEBUG:
            print "setEnables: SEND: %s\t RCVD: %s"%(command, answer)

    def setEnables(self, enables):
        self.StopAdc()
        self._setEnables(enables)
        self.StartAdc()

    def setEnablesAll(self, enable):
        self.StopAdc()
        self.setEnables([['1', enable], ['2', enable], ['3', enable], ['4', enable]])
        self.StartAdc()

    def disableAll(self):
        self.setEnables([['1', 'NO'],['2', 'NO'],['3', 'NO'],['4', 'NO']])

    def enableChannel(self, channel):
        self.setEnables([['%s'%channel, 'YES']])

    def getInvs(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?INV %s'%channelchain
            answer = self.ask(command)
            invs = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getInvs: %s"%(e)
            return None
        if self.DEBUG:
            print "getInvs: SEND: %s\t RCVD: %s"%(command, answer)
            print "getInvs: %s"%(invs)
        return invs

    def getInvsAll(self):
        self.getInvs(['1', '2', '3', '4'])

    def _setInvs(self, invs):
        channelchain = ''
        for couple in invs:
            channelchain = '%s %s %s '%(channelchain, couple[0], couple[1])
        try: 
            command = 'INV %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'INV ACK\x00':
                raise Exception('setInvs: Wrong acknowledge')
        except Exception, e:
            print "setInvs: %s"%(e)
        if self.DEBUG:
            print "setInvs: SEND: %s\t RCVD: %s"%(command, answer)

    def setInvs(self, invs):
        self.StopAdc()
        self._setInvs(invs)
        self.StartAdc()

    def setInvsAll(self, inv):
        self.StopAdc()
        self.setInvs([['1', inv], ['2', inv], ['3', inv], ['4', inv]])
        self.StartAdc()

    def getFilters(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?FILTER %s'%channelchain
            answer = self.ask(command)
            filters = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getFilters: %s"%(e)
            return None
        if self.DEBUG:
            print "getFilters: SEND: %s\t RCVD: %s"%(command, answer)
            print "getFilters: %s"%(filters)
        return filters

    def getFiltersAll(self):
        self.getFilters(['1', '2', '3', '4'])

    def _setFilters(self, filters):
        channelchain = ''
        for couple in filters:
            channelchain = '%s %s %s '%(channelchain, couple[0], couple[1])
        '''
        try:
            for couple in filters:
               channelchain = '%s %s'%(couple[0], couple[1])
               command = 'FILTER %s'%(channelchain)
               answer = self.ask(command)
        '''
        try: 
            command = 'FILTER %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'FILTER ACK\x00':
                raise Exception('setFilters: Wrong acknowledge')
        except Exception, e:
            print "setFilters: %s"%(e)
        if self.DEBUG:
            print "setFilters: SEND: %s\t RCVD: %s"%(command, answer)

    def setFilters(self, filters):
        self.StopAdc()
        self._setFilters(filters)
        self.StartAdc()

    def setFiltersAll(self, filter):
        self.StopAdc()
        self.setFilters([['1', filter], ['2', filter], ['3', filter], ['4', filter]])
        self.StartAdc()

    def getOffsets(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?OFFSET %s'%channelchain
            answer = self.ask(command)
            offsets = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getOffsets: %s"%(e)
            return None
        if self.DEBUG:
            print "getOffsets: SEND: %s\t RCVD: %s"%(command, answer)
            print "getOffsets: %s"%(offsets)
        return offsets

    def getOffsetsAll(self):
        self.getOffsets(['1', '2', '3', '4'])

    def _setOffsets(self, offsets):
        channelchain = ''
        for couple in offsets:
            channelchain = '%s %s %s '%(channelchain, couple[0], couple[1])
        try: 
            command = 'OFFSET %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'OFFSET ACK\x00':
                raise Exception('setOffsets: Wrong acknowledge')
        except Exception, e:
            print "setOffsets: %s"%(e)
        if self.DEBUG:
            print "setOffsets: SEND: %s\t RCVD: %s"%(command, answer)

    def setOffsets(self, offsets):
        self.StopAdc()
        self._setOffsets(offsets)
        self.StartAdc()

    def setOffsetsAll(self, offset):
        self.StopAdc()
        self.setOffsets([['1', offset], ['2', offset], ['3', offset], ['4', offset]])
        self.StartAdc()

    def getAmpmodes(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?AMPMODE %s'%channelchain
            answer = self.ask(command)
            ampmodes = self.extractMultichannel(answer, 1)
        except Exception, e:
            print "getAmpmodes: %s"%(e)
            return None
        if self.DEBUG:
            print "getAmpmodes: SEND: %s\t RCVD: %s"%(command, answer)
            print "getAmpmodes: %s"%(ampmodes)
        return ampmodes

    def getAmpmodesAll(self):
        self.getAmpmodes(['1', '2', '3', '4'])

    def _setAmpmodes(self, ampmodes):
        channelchain = ''
        for couple in ampmodes:
            channelchain = '%s %s %s '%(channelchain, couple[0], couple[1])
        try: 
            command = 'AMPMODE %s'%(channelchain)
            answer = self.ask(command)
            if answer != 'AMPMODE ACK\x00':
                raise Exception('setAmpmodes: Wrong acknowledge')
        except Exception, e:
            print "setAmpmodes: %s"%(e)
        if self.DEBUG:
            print "setAmpmodes: SEND: %s\t RCVD: %s"%(command, answer)

    def setAmpmodes(self, ampmodes):
        self.StopAdc()
        self._setAmpmodes(ampmodes)
        self.StartAdc()

    def setAmpmodesAll(self, ampmode):
        self.StopAdc()
        self.setAmpmodes([['1', ampmode], ['2', ampmode], ['3', ampmode], ['4', ampmode]])

    def getMeasures(self, channels):
        channelchain = ''
        for channel in channels:
            channelchain ='%s %s '%(channelchain, channel)
        try:
            command = '?MEAS %s'%channelchain
            answer = self.ask(command)
            #print "getMeasures: SEND: %s\t RCVD: %s"%(command, answer)
            measures, status = self.extractMultichannel(answer, 1)
            #print "getMeasures: %s, %s"%(measures, status)
        except Exception, e:
            print "getMeasures: %s"%(e)
            return None
        if self.DEBUG:
            print "getMeasures: SEND: %s\t RCVD: %s"%(command, answer)
            print "getMeasures: %s, %s"%(measures, status)
        return measures, status

    def getMeasure(self, channel):
        try:
            command = '?MEAS'
            answer = self.ask(command)
            #print "getMeasure: SEND: %s\t RCVD: %s"%(command, answer)
            measure, status = self.extractMultichannel(answer, 1)
            #print "getMeasure: %s, %s"%(measure, status)
        except Exception, e:
            #print "getMeasure: %s"%(e)
            return None
        if self.DEBUG:
            print "getMeasure: SEND: %s\t RCVD: %s"%(command, answer)
            print "getMeasure: %s, %s"%(measure, status)
            print "getMeasure: %s"%(measure[int(channel[0])-1][1])
        return measure[int(channel[0])-1][1]

    def getMeasuresAll(self):
        self.getMeasures(['1', '2', '3', '4'])

    def getAvsamples(self):
        try:
            command = '?AVSAMPLES'
            answer = self.ask(command)
            avsamples = self.extractSimple(answer)
        except Exception, e:
            print "getAvsamples: %s"%(e)
            return None
        if self.DEBUG:
            print "getAvsamples: SEND: %s\t RCVD: %s"%(command, answer)
            print "getAvsamples: %s"%(avsamples)
        return avsamples

    def _setAvsamples(self, avsamples):
        try: 
            command = 'AVSAMPLES %s'%(avsamples)
            answer = self.ask(command)
            if answer != 'AVSAMPLES ACK\x00':
                raise Exception('setAvsamples: Wrong acknowledge')
        except Exception, e:
            print "setAvsamples: %s"%(e)
            print "setAvsamples: SEND: %s\t RCVD: %s"%(command, answer)
        if self.DEBUG:
            print "setAvsamples: SEND: %s\t RCVD: %s"%(command, answer)

    def setAvsamples(self, avsamples):
        self.StopAdc()
        self._setAvsamples(avsamples)
        self.StartAdc()

    def getPoints(self):
        try:
            command = '?POINTS'
            answer = self.ask(command)
            points = self.extractSimple(answer)
        except Exception, e:
            print "getPoints: %s"%(e)
            return None
        if self.DEBUG:
            print "getPoints: SEND: %s\t RCVD: %s"%(command, answer)
            print "getPoints: %s"%(points)
        return points

    def _setPoints(self, points):
        try: 
            command = 'POINTS %s'%(points)
            answer = self.ask(command)
            if answer != 'POINTS ACK\x00':
                raise Exception('setPoints: Wrong acknowledge')
        except Exception, e:
            print "setPoints: %s"%(e)
        if self.DEBUG:
            print "setPoints: SEND: %s\t RCVD: %s"%(command, answer)

    def setPoints(self, points):
        self.StopAdc()
        self._setPoints(points)
        self.StartAdc()

    def getTrigperiod(self):
        try:
            command = '?TRIGPERIODE'
            if self.DEBUG: print 'getTrigperiod: Sending command...'
            answer = self.ask(command)
            trigperiode = self.extractSimple(answer)
        except Exception, e:
            print "getTrigperiod: %s"%(e)
            return None
        if self.DEBUG:
            print "getTrigperiod: SEND: %s\t RCVD: %s"%(command, answer)
            print "getTrigperiod: %s"%(trigperiode)
        return trigperiode

    def _setTrigperiod(self, trigperiod):
        try: 
            command = 'TRIGPERIODE %s'%(trigperiod)
            answer = self.ask(command)
            if answer != 'TRIGPERIODE ACK\x00':
                raise Exception('setTrigperiod: Wrong acknowledge')
        except Exception, e:
            print "setTrigperiod: %s"%(e)
        if self.DEBUG:
            print "setTrigperiod: SEND: %s\t RCVD: %s"%(command, answer)

    def setTrigperiod(self, trigperiod):
        self.StopAdc()
        self._setTrigperiod(trigperiod)
        self.StartAdc()

    def getSrate(self):
        try:
            command = '?SRATE'
            answer = self.ask(command)
            srate = self.extractSimple(answer)
        except Exception, e:
            print "getSrate: %s"%(e)
            return None
        if self.DEBUG:
            print "getSrate: SEND: %s\t RCVD: %s"%(command, answer)
            print "getSrate: %s"%(srate)
        return srate

    def _setSrate(self, srate):
        try: 
            command = 'SRATE %s'%(srate)
            answer = self.ask(command)
            if answer != 'SRATE ACK\x00':
                raise Exception('setSrate: Wrong acknowledge')
        except Exception, e:
            print "setSrate: %s"%(e)
        if self.DEBUG:
            print "setSrate: SEND: %s\t RCVD: %s"%(command, answer)

    def setSrate(self, srate):
        self.StopAdc()
        self._setSrate(srate)
        self.StartAdc()

    def getState(self):
        try:
            command = '?STATE'
            answer = self.ask(command)
            state = self.extractSimple(answer)
        except Exception, e:
            print "getState: %s"%(e)
            return None
        if self.DEBUG:
            print "getState: SEND: %s\t RCVD: %s"%(command, answer)
            print "getState: %s"%(state)
        return state

    def getStatus(self):
        try:
            command = '?STATUS'
            answer = self.ask(command)
            status = self.extractSimple(answer)
        except Exception, e:
            print "getStatus: %s"%(e)
            return None
        if self.DEBUG:
            print "getStatus: SEND: %s\t RCVD: %s"%(command, answer)
            print "getStatus: %s"%(status)
        return status

    def getMode(self):
        try:
            command = '?MODE'
            answer = self.ask(command)
            mode = self.extractSimple(answer)
        except Exception, e:
            print "getMode: %s"%(e)
            return None
        if self.DEBUG:
            print "getMode: SEND: %s\t RCVD: %s"%(command, answer)
            print "getMode: %s"%(mode)
        return mode

    def Start(self):
        try: 
            command = 'START'
            answer = self.ask(command)
            if answer != 'START ACK\x00':
                raise Exception('Start: Wrong acknowledge')
        except Exception, e:
            print "Start: %s"%(e)
        if self.DEBUG:
            print "Start: SEND: %s\t RCVD: %s"%(command, answer)

    def StartAdc(self):
        try: 
            command = 'STARTADC'
            answer = self.ask(command)
            if answer != 'STARTADC ACK\x00':
                raise Exception('StartAdc: Wrong acknowledge')
        except Exception, e:
            print "StartAdc: %s"%(e)
        if self.DEBUG:
            print "StartAdc: SEND: %s\t RCVD: %s"%(command, answer)

    def StopAdc(self):
        try: 
            command = 'STOPADC'
            answer = self.ask(command)
            if answer != 'STOPADC ACK\x00':
                raise Exception('StopAdc: Wrong acknowledge')
        except Exception, e:
            print "StopAdc: %s"%(e)
        if self.DEBUG:
            print "StopAdc: SEND: %s\t RCVD: %s"%(command, answer)

    def Stop(self):
        try: 
            command = 'STOP'
            answer = self.ask(command)
            if answer != 'STOP ACK\x00':
                raise Exception('Stop: Wrong acknowledge')
        except Exception, e:
            print "Stop: %s"%(e)
        if self.DEBUG:
            print "Stop: SEND: %s\t RCVD: %s"%(command, answer)

        
    def tryToConnect(self):
        try:
            if self.connected == False:
                ping = subprocess.Popen(
                                        ['ping','c','2',self.host],
                                        stdout = subprocess.PIPE,
                                        stderr = subprocess.PIPE
                                        )

                out, err = ping.communicate()
                if out.find('Destination Host Unreachable') == -1:
                    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    self.sock.settimeout(1)
                    self.connected = True
                else:
                    self.connected = False

        except socket.timeout, timeout:
            self.connected = False
        except Exception, e:
            self.connected = False             




if __name__ == "__main__":
    # TWO BASIC PARAMETERS, unit address and channel 
    #Substitute ask by ask2 in order to use savechain method for debugging without hw
    myalbaem = albaem('elem01r42-013-bl13.cells.es')
    emu = False
    myalbaem.DEBUG = True
    print myalbaem.getRangesAll()
    print myalbaem.setRangesAll('1mA')
    print myalbaem.getRangesAll()
    print myalbaem.setRangesAll('100uA')
    print myalbaem.getRangesAll()
    print myalbaem.getFiltersAll()
    print myalbaem.setFiltersAll('NO')
    print myalbaem.getFiltersAll()
    print myalbaem.setFiltersAll('10')
    print myalbaem.getFiltersAll()
    print myalbaem.getInvsAll()
    print myalbaem.setInvsAll('NO')
    print myalbaem.getInvsAll()
    print myalbaem.setInvsAll('YES')
    print myalbaem.getInvsAll()
    print myalbaem.getOffsetsAll()
    print myalbaem.getEnablesAll()
    print myalbaem.getAmpmodesAll()
    print myalbaem.setAmpmodesAll('HB')
    print myalbaem.getAmpmodesAll()
    print myalbaem.setAmpmodesAll('LN')
    print myalbaem.getAmpmodesAll()
    print myalbaem.getAvsamples()
    print myalbaem.getTrigperiod()
    print myalbaem.getPoints()
    
    
