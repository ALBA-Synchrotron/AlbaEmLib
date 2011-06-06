

import sys
#import pyIcePAP
import time
import PyTango
from pylab import *
import array
from scipy.stats import *
import socket
import datetime

from threading import Lock


#tango://localhost:10000/ws/bl01/serial0
class albaem():
    ''' The configuration of the serial line is: 8bits + 1 stopbit, bdr: 9600, terminator:none'''
    ''' The cable is crossed'''
    myalbaemds = None
    DEBUG = False

    def __init__(self, host, port=7):
        self.DEBUG = False
        self.host = host
        self.port = port
        self.lock = Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1)

        self.logFileName = 'albaemlib.log'
        fd = open(self.logFileName, 'a')
        stringToSave ='\n\n-----New Instance at: ' + str(datetime.datetime.now()) + '-----\n' 
        fd.write(stringToSave)
        fd.close()

    def savechain(self, savedchain):
        self.savedchain = savedchain+'\x00'

    def ask2(self, cmd, size=8192):
        print "ask: %s"%self.savedchain
        return self.savedchain
    def ask(self, cmd, size=8192):
        try:
            fd = open(self.logFileName, 'a')
            self.lock.acquire()
            #print "------>lock acquired------"
            stringToSave = str(datetime.datetime.now()) + ' -->Sending command' + cmd + '\n'
            self.sock.sendto(cmd, (self.host, self.port))
            stringToSave = stringToSave + str(datetime.datetime.now()) + ' -->    Command sended\n'
            #print "----------->command sended"
            data = self.sock.recv(size)
            print "----------->received data"
            # SHOULD MAKE SURE ALL DATA IS RECEIVED data.endswith('\x00')?
            if self.DEBUG:
                print 'AlbaEM DEBUG: query:',cmd,'\t','answer length:', len(data), '\t', 'answer:#%s#'%(data)
            #if not data.endswith('\x00'):
	        #print "null char missing, releasing lock..."
 	        #self.lock.release() #This lock might not be necessary, the last except catches the generated exception unlocks and prints the causing exception. If we unlock here, then there's a double unlock exception and the heredown generated doesn't show up
            #    raise Exception('Wrong termination' , data)
            #print "Normal lock release"
            #self.lock.release()
            return data
         
        except socket.timeout, timeout:
            #self.lock.release()
            stringToSave = stringToSave + str(datetime.datetime.now()) + ' Timeout Error\n'
            fd.write(stringToSave)
            print 'Timeout Error'
            return '100'
            raise Exception('Socket timeout', timeout)
        except socket.error, error:
            #self.lock.release()
            stringToSave = stringToSave + str(datetime.datetime.now()) + ' Socket Error\n'
            fd.write(stringToSave)
            print 'Socket Error'
            return '200'
            raise Exception('Socket error', error)
        except Exception, e:
            print 'Unknown Error'
            return '300'
            #self.lock.release()
            stringToSave = stringToSave + str(datetime.datetime.now()) + ' Unknown Error\n'
            fd.write(stringToSave)
            raise Exception('Unknown exception', e)
        finally:
            fd.close()
            self.lock.release()
            #return '400'
            #print "------>lock released------"

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
    def setRanges(self, ranges):
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
    def setEnables(self, enables):
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
    def setInvs(self, invs):
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
    def setFilters(self, filters):
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
    def setOffsets(self, offsets):
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
    def setAvsamples(self, avsamples):
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
    def setPoints(self, points):
        try: 
            command = 'POINTS %s'%(points)
            answer = self.ask(command)
            if answer != 'POINTS ACK\x00':
                raise Exception('setPoints: Wrong acknowledge')
        except Exception, e:
            print "setPoints: %s"%(e)
        if self.DEBUG:
            print "setPoints: SEND: %s\t RCVD: %s"%(command, answer)
    def getTrigperiode(self):
        try:
            command = '?TRIGPERIODE'
            if self.DEBUG: print 'getTrigperiode: Sending command...'
            answer = self.ask(command)
            trigperiode = self.extractSimple(answer)
        except Exception, e:
            print "getTrigperiode: %s"%(e)
            return None
        if self.DEBUG:
            print "getTrigperiode: SEND: %s\t RCVD: %s"%(command, answer)
            print "getTrigperiode: %s"%(trigperiode)
        return trigperiode
    def setTrigperiode(self, trigperiode):
        try: 
            command = 'TRIGPERIODE %s'%(trigperiode)
            answer = self.ask(command)
            if answer != 'TRIGPERIODE ACK\x00':
                raise Exception('setTrigperiode: Wrong acknowledge')
        except Exception, e:
            print "setTrigperiode: %s"%(e)
        if self.DEBUG:
            print "setTrigperiode: SEND: %s\t RCVD: %s"%(command, answer)
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
    def setSrate(self, srate):
        try: 
            command = 'SRATE %s'%(srate)
            answer = self.ask(command)
            if answer != 'SRATE ACK\x00':
                raise Exception('setSrate: Wrong acknowledge')
        except Exception, e:
            print "setSrate: %s"%(e)
        if self.DEBUG:
            print "setSrate: SEND: %s\t RCVD: %s"%(command, answer)
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

        




if __name__ == "__main__":
    # TWO BASIC PARAMETERS, unit address and channel 
    #Substitute ask by ask2 in order to use savechain method for debugging without hw
    myalbaem = albaem('emprot01.cells.es')
    emu = False
    if emu:    myalbaem.savechain('?RANGE 1 1mA 2 1mA 3 100pA')
    print myalbaem.getRanges(['1', '2', '3'])
    if emu:    myalbaem.savechain('?OFFSET 1 0.1 3 -0.1 4 0.2')
    print myalbaem.getOffsets(['1', '3', '4'])
    if emu:    myalbaem.savechain('?INV 1 YES 3 YES 4 YES')
    print myalbaem.getInvs(['1', '3', '4'])
    if emu:    myalbaem.savechain('?FILTER 1 1 4 10')
    print myalbaem.getFilters(['1', '4'])
    if emu:    myalbaem.savechain('?ENABLE 1 YES 2 YES 3 YES 4 YES')
    print myalbaem.getEnables(['1', '2', '3','4'])
    #if emu:    myalbaem.savechain('?TRIGPERIODE 10')
    #print myalbaem.getTrigperiode()
    if emu:    myalbaem.savechain('START ACK')
    print myalbaem.Start()
    #if emu:    myalbaem.savechain('START ACK\x00')
    #print myalbaem.Start()
    #if emu:    myalbaem.savechain('STOP ACK\x00')
    #print myalbaem.Stop()
    if emu:    myalbaem.savechain('?AVSAMPLES 1000')
    print myalbaem.getAvsamples()
    if emu:    myalbaem.savechain('?MEAS 1 1e-10 2 1e-11 3 1e-6 4 1e-3 AEEA')
    print myalbaem.getMeasures(['1','2', '3', '4'])
    
