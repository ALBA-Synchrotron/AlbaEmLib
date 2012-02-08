

import sys
#import pyIcePAP
import time
import PyTango
#from pylab import *
import array
from scipy.stats import *
import socket
import datetime

from threading import Lock


class AlbaEmLogger():
    """ Class for log the errors in a file 
    """
    
    def __init__(self, filename, record=True):
        self._fileName = filename
        self._record = record
        
        stringToLog = '\n\n+-----------------' + str(datetime.datetime.now()) +'----------------------+ \n' \
                      '+--------------------------+---------------------+----------------+ \n' \
                      '|         Date time        |      Error Root     |   Error Type   | \n' \
                      '+--------------------------+---------------------+----------------+ \n'
        self.logString(stringToLog)
        
    def getFileName(self):
        return self._fileName
    
    def setFileName(self, filename):
        self._fileName = filename
        
    def getRecordState(self):
        return self._record
    
    def setRecordState(self, state):
        self._record = state
    
    def logString(self, stringToLog):
        if self._record:
            fd = open(self._fileName, 'a')
            fd.write(stringToLog)
            fd.close()
        
    def log(self, date, error, type):
        if self._record:
            stringToLog = str(date) + ' | ' + str(error) + ' | ' + str(type) + '\n'
            fd = open(self._fileName, 'a')
            fd.write(stringToLog)
            fd.close()

#tango://localhost:10000/ws/bl01/serial0
class albaem():
    ''' The configuration of the serial line is: 8bits + 1 stopbit, bdr: 9600, terminator:none'''
    ''' The cable is crossed'''
    myalbaemds = None
    DEBUG = False

    def __init__(self, host, port=7, record=True):
        self.logger = AlbaEmLogger('ErrorsLog.log',record)
        self.DEBUG = False
        self.host = host
        self.port = port
        self.lock = Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)

    def savechain(self, savedchain):
        self.savedchain = savedchain+'\x00'

    def ask2(self, cmd, size=8192):
        print "ask: %s"%self.savedchain
        return self.savedchain

    def ask(self, cmd, size=8192):
        try:
            #stringToSave = ''
            self.lock.acquire()
            #stringToSave = str(datetime.datetime.now()) + ' -->Sending command' + cmd + '\n'
            self.sock.sendto(cmd, (self.host, self.port))
            #stringToSave = stringToSave + str(datetime.datetime.now()) + ' -->    Command sended\n'
            data = self.sock.recv(size)
            #@warning: this is a fast test for Julio, better to remove it when the bug will be solved
            self.Command = cmd + ': ' + str(data) + '\n'
            if data.startswith('?ERROR') or data.startswith('ERROR'):
                self.logger.logString(str(cmd) + '-->' + str(datetime.datetime.now())+str(data))
            if self.DEBUG:
                print 'AlbaEM DEBUG: query:',cmd,'\t','answer length:', len(data), '\t', 'answer:#%s#'%(data)

            return data
         
        except socket.timeout, timeout:
            #stringToSave = stringToSave + str(datetime.datetime.now()) + ' Timeout Error\n'
            self.logger.log(datetime.datetime.now(), '        ask        ', 'Timeout')
            try:
                if self.connected:
                    #stringToSave = stringToSave + str(datetime.datetime.now()) + ' -->Sending command' + cmd + '\n'
                    self.sock.sendto(cmd, (self.host, self.port))
                    #stringToSave = stringToSave + str(datetime.datetime.now()) + ' -->    Command sended\n'
                    data = self.sock.recv(size)
                    self.Command = cmd + ': ' + str(data) + '\n'
                    if data.startswith('?ERROR') or data.startswith('ERROR'):
                        self.logger.logString(str(cmd) + '-->' + str(datetime.datetime.now())+str(data))
                else:
                    self.logger.log(datetime.datetime.now(), '        ask        ', 'Timeout')
                    raise Exception('Device not found!')
                return data
            except Exception, e:
                self.logger.log(datetime.datetime.now(), '        ask        ', 'Unknown')
                print 'Timeout Error'
                return 'Socket timeout'
            
        except socket.error, error:
            print 'Socket Error'
            return 'Socket Error'
            #stringToSave = stringToSave + str(datetime.datetime.now()) + ' Socket Error\n'
            self.logger.log(datetime.datetime.now(), '        ask        ', 'Socket')
            #self.lock.release()
            #raise Exception('Socket error', error)
        except Exception, e:
            print 'Unknown Error'
            return 'Unknown Exception'
            #stringToSave = stringToSave + str(datetime.datetime.now()) + ' Unknown Error\n'
            self.logger.log(datetime.datetime.now(), '        ask        ', 'Unknown')
            #self.lock.release()
            #raise Exception('Unknown exception', e)
        finally:
            self.lock.release()

    def extractMultichannel(self, chain, initialpos):
        answersplit = chain.strip('\x00').split(' ')
        if answersplit[0] == '?MEAS':
            status = answersplit[len(answersplit) - 1]
            parameters = answersplit[initialpos:len(answersplit)-1]
            print parameters
        else:
            parameters = answersplit[initialpos:len(answersplit)]
            print parameters
        couples = []
        if len(parameters)%2 != 0:
            #stringToSave = str(datetime.datetime.now()) + ' Error in extractMultichannel: Wrong number of parameters ' + str(parameters) + '\n'
            self.logger.log(datetime.datetime.now(), 'extractMultichannel', str(parameters))
            self.logger.logString(self.Command)
            raise Exception('extractMultichannel: Wrong number of parameters')
        for i in range(0, len(parameters)/2):
            if parameters[i*2] in ['1', '2', '3', '4']:
                couples.append([parameters[i*2], parameters[i*2 + 1]])
            else: 
                #stringToSave = str(datetime.datetime.now()) + ' Error in extractMultichannel: Wrong channel ' + str(parameters + '\n')
                #self.logger.log(stringToSave)
                self.logger.log(datetime.datetime.now(), 'extractMultichannel', str(parameters))
                self.logger.logString(self.Command)
                raise Exception('extractMultichannel: Wrong channel')
        if self.DEBUG:
            print "extractMultichannel:%s"%(couples)
        if answersplit[0] == '?MEAS':
            return couples, status
        elif answersplit[0] == '?LDATA' or answersplit[0].startswith('?DATA'):
            return couples, status, lastpos
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
        return self.getRanges(['1', '2', '3', '4'])

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
        return self.getEnables(['1', '2', '3', '4'])

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
        return self.getInvs(['1', '2', '3', '4'])

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
        return self.getFilters(['1', '2', '3', '4'])

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
        return self.getOffsets(['1', '2', '3', '4'])

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
        return self.getAmpmodes(['1', '2', '3', '4'])

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

    def getLdata(self):
        channelchain = ''
        try:
            command = '?LDATA'
            answer = self.ask(command)
            #print "getLdata: SEND: %s\t RCVD: %s"%(command, answer)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                lastpos = 0
                measures = []
                status = ''
            #print "getLdata: %s, %s"%(measures, status)
        except Exception, e:
            print "getLdata: %s"%(e)
            return None
        if self.DEBUG:
            print "getLdata: SEND: %s\t RCVD: %s"%(command, answer)
            print "getLdata: %s, %s %s"%(measures, status, lastpos)
        return measures, status, lastpos

    def getData(self, position):
        channelchain = ''
        try:
            command = '?DATA %s'%position
            answer = self.ask(command)
            #print "getLdata: SEND: %s\t RCVD: %s"%(command, answer)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                lastpos = 0
                measures = ''
                status = ''
            #print "getLdata: %s, %s"%(measures, status)
        except Exception, e:
            print "getLdata: %s"%(e)
            return None
        if self.DEBUG:
            print "getLdata: SEND: %s\t RCVD: %s"%(command, answer)
            print "getLdata: %s, %s"%(measures, status, lastpos)
        return measures, status, lastpos
        
    
    def getLastpos(self):
        measures, status, lastpos = self.getLdata()
        return lastpos

    def getBuffer(self):
        lastpos = self.getLastpos()
        thebuffer = []
        for i in range(0, lastpos):
            measures, status, lastpos = self.getData(i) #getLdata() bug included by Mr. JLidon
            #print measures, status, lastpos
            thebuffer.append([float(measures[0][1]), float(measures[1][1]), float(measures[2][1]), float(measures[3][1])])
        #print thebuffer
        return thebuffer
    
    def getBufferChannel(self, chan):
        if chan in range(1, 5):
          abuffer = self.getBuffer()
          channelbuffer = []
          for i in range(0, len(abuffer)):
              channelbuffer.append(abuffer[i][chan-1])
          return channelbuffer
        else:
          raise Exception('getBufferChannel: Wrong channel (1-4)')

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
        return self.getMeasures(['1', '2', '3', '4'])

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

    def getTrigmode(self):
        try:
            command = '?TRIGMODE'
            if self.DEBUG: print 'getTrigmode: Sending command...'
            answer = self.ask(command)
            trigmode = self.extractSimple(answer)
        except Exception, e:
            print "getTrigmode: %s"%(e)
            return None
        if self.DEBUG:
            print "getTrigmode: SEND: %s\t RCVD: %s"%(command, answer)
            print "getTrigmode: %s"%(trigmode)
        return trigmode

    def _setTrigmode(self, trigmode):
        try: 
            command = 'TRIGMODE %s'%(trigmode)
            answer = self.ask(command)
            if answer != 'TRIGMODE ACK\x00':
                raise Exception('setTrigmode: Wrong acknowledge')
        except Exception, e:
            print "setTrigmode: %s"%(e)
        if self.DEBUG:
            print "setTrigmode: SEND: %s\t RCVD: %s"%(command, answer)

    def setTrigmode(self, trigmode):
        self.StopAdc()
        self._setTrigmode(trigmode)
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

    def getInfo(self):
        print 'Ranges:', self.getRangesAll()
        print 'Filters:', self.getFiltersAll()
        print 'Invs:', self.getInvsAll()
        print 'Offsets:', self.getOffsetsAll()
        print 'Ampmodes:', self.getAmpmodesAll()
        print 'Avsamples:', self.getAvsamples()

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

    def sendSetCmd(self, cmd):
        self.StopAdc()
        self.ask(cmd)
        self.StartAdc()    

    def clearOffsetCorr(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        self.StopAdc()
        for range in ranges:
            self.ask('OFFSETCORR %s 1 0 2 0 3 0 4 0'%range)
        self.StartAdc()

    def getOffsetCorrAll(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for range in ranges:
            print self.ask('?OFFSETCORR %s'%range)

    def getGainCorrAll(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for range in ranges:
            print self.ask('?GAINCORR %s'%range)

    def resetGainCorr(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for range in ranges:
            print self.sendSetCmd('GAINCORR %s %s 1'%(range, channel))

    def resetOffsetCorr(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for range in ranges:
            print self.sendSetCmd('OFFSETCORR %s %s 0'%(range, channel))

    def toggleGainCorrPolarisation(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        gaincorrs = []
        for range in ranges:
            gaincorr = self.ask('?GAINCORR %s'%range).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        print "Initial gaincorr factors:"
        for gc in gaincorrs:
            print gc
        self.StopAdc()
        for range in ranges:
            #print 'GAINCORR %s %s %s'%(range, channel, -1*float(gaincorrs[ranges.index(range)][2+2*int(channel)-1]))
            self.ask('GAINCORR %s %s %s'%(range, channel, -1*float(gaincorrs[ranges.index(range)][2+2*int(channel)-1])))
        self.StartAdc()
        gaincorrs = []
        for range in ranges:
            gaincorr = self.ask('?GAINCORR %s'%range).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        print "Final gaincorr factors:"
        for gc in gaincorrs:
            print gc
    
    def loadConfig(self, loadfile):
        cmd = []
        myfile = open(loadfile, 'r')
        mylogstring = myfile.readlines()
        for i in range(0,6):
            mystring = mylogstring[i].strip('\n').split(',')
            cmd.append("%s 1 %s 2 %s 3 %s 4 %s"%(mystring[0], mystring[1], mystring[2], mystring[3], mystring[4]))
        for i in range(6,len(mylogstring)):
            mystring = mylogstring[i].strip('\n').split(',')
            cmd.append("%s %s 1 %s 2 %s 3 %s 4 %s"%(mystring[0], mystring[1], mystring[2], mystring[3], mystring[4], mystring[5]))
        print "Loading config to EM:"
        for c in cmd:
            print c
            self.sendSetCmd(c)
 
    def _dumpConfig(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        mylogstring = []
        mystring = self.ask('?RANGE').strip('\x00').split(' ')
        mylogstring.append("RANGE,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        mystring = self.ask('?FILTER').strip('\x00').split(' ')
        mylogstring.append("FILTER,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        mystring = self.ask('?INV').strip('\x00').split(' ')
        mylogstring.append("INV,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        mystring = self.ask('?OFFSET').strip('\x00').split(' ')
        mylogstring.append("OFFSET,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        mystring = self.ask('?ENABLE').strip('\x00').split(' ')
        mylogstring.append("ENABLE,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        mystring = self.ask('?AMPMODE').strip('\x00').split(' ')
        mylogstring.append("AMPMODE,%s,%s,%s,%s\n"%(mystring[2], mystring[4], mystring[6], mystring[8]))
        for range in ranges:
            mystring = self.ask('?OFFSETCORR %s'%range).strip('\x00').split(' ')
            mylogstring.append("OFFSETCORR,%s,%s,%s,%s,%s\n"%(range, mystring[3], mystring[5], mystring[7], mystring[9]))
        for range in ranges:
            mystring = self.ask('?GAINCORR %s'%range).strip('\x00').split(' ')
            mylogstring.append("GAINCORR,%s,%s,%s,%s,%s\n"%(range, mystring[3], mystring[5], mystring[7], mystring[9]))
        return mylogstring

    def dumpConfig(self, dumpfile):
        mylogstring = self._dumpConfig()
        myfile = open(dumpfile, 'w') 
        print "Dumping config to file: %s"%dumpfile
        for line in mylogstring:
            print line.strip('\n')
            myfile.write(line)

    def dumpDefaultConfig(self):
        self.dumpConfig('./%s.dump'%self.host)

    def loadDefaultConfig(self):
        self.loadConfig('./%s.dump'%self.host)

    def checkAgainstDumpedConfig(self, dumpfile):
        mylogstring = self._dumpConfig()
        myfile = open(dumpfile, 'r')
        mydumpedstring = myfile.readlines()
        missmatches = 0
        print "Comparing config of em %s with dumpfile %s..."%(self.host, dumpfile)
        for i in range(0, len(mylogstring)):
            if mylogstring[i] != mydumpedstring[i]:
                print "Current config and dumped config missmatch:"
                print "Current: %s"%mylogstring[i].strip('\n')
                print "Dump file: %s"%mydumpedstring[i].strip('\n')
                missmatches = missmatches + 1
        print "Comparison finished. Number of missmatches:%s"%missmatches

    def checkAgainstDefaultDumpedConfig(self):
        self.checkAgainstDumpedConfig('./%s.dump'%self.host)

        

if __name__ == "__main__":
    # TWO BASIC PARAMETERS, unit address and channel 
    #Substitute ask by ask2 in order to use savechain method for debugging without hw
    myalbaem = albaem('elem01r42-013-bl13.cells.es')
    '''
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
    myalbaem.dumpEM('./em.dump')
    myalbaem.loadEM('./em.dump')
    '''
    myalbaem.dumpDefaultConfig()
    myalbaem.checkAgainstDefaultDumpedConfig()
    myalbaem.loadDefaultConfig()
