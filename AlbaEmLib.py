
import time
import array
from scipy.stats import *
import socket
import datetime
import logging
import logging.handlers

from threading import Lock


#class AlbaEmLogger():
#    """ Class for log the errors in a file 
#    """
#    
#    def __init__(self, filename, record=True):
#        self._fileName = filename
#        self._record = record
#        
#        stringToLog = '\n\n+-----------------' + str(datetime.datetime.now()) +'----------------------+ \n' \
#                      '+--------------------------+---------------------+----------------+ \n' \
#                      '|         Date time        |      Error Root     |   Error Type   | \n' \
#                      '+--------------------------+---------------------+----------------+ \n'
#        self.logString(stringToLog)
#        
#    def getFileName(self):
#        return self._fileName
#    
#    def setFileName(self, filename):
#        self._fileName = filename
#        
#    def getRecordState(self):
#        return self._record
#    
#    def setRecordState(self, state):
#        self._record = state
#    
#    def logString(self, stringToLog):
#        if self._record:
#            fd = open(self._fileName, 'a')
#            fd.write(stringToLog)
#            fd.close()
#        
#    def log(self, date, error, type):
#        if self._record:
#            stringToLog = str(date) + ' | ' + str(error) + ' | ' + str(type) + '\n'
#            fd = open(self._fileName, 'a')
#            fd.write(stringToLog)
#            fd.close()

class albaem():
    ''' The configuration of the serial line is: 8bits + 1 stopbit, bdr: 9600, terminator:none'''
    ''' The cable is crossed'''
    myalbaemds = None
    DEBUG = False

    def __init__(self, host, logFileName='AlbaEmLog.log', port=7, record=True):
        #self.logger = AlbaEmLogger(logFileName,record)
        #DftLogFormat = '%(threadName)-14s %(levelname)-8s %(asctime)s %(name)s: %(message)s'
        #logging.basicConfig(filename=logFileName,format=DftLogFormat,level=logging.DEBUG)
        
        self.logger = logging.Logger("albaEM")
        self.logger.setLevel(logging.INFO)
        
        self.DEBUG = False
        self.host = host
        self.port = port
        self.lock = Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(0.1)

    def savechain(self, savedchain):
        self.savedchain = savedchain+'\x00'

    def ask2(self, cmd, size=8192):
        #print "ask: %s"%self.savedchain
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
            self.logger.debug("Testing")
            if data.startswith('?ERROR') or data.startswith('ERROR'):
                self.logger.debug('Command: %s Data: %s' ,cmd,data)

            self.logger.debug('AlbaEM DEBUG: query:',cmd,'\t','answer length:', len(data), '\t', 'answer:#%s#'%(data))
            return data
         
        except socket.timeout, timeout:
            #stringToSave = stringToSave + str(datetime.datetime.now()) + ' Timeout Error\n'
            #self.logger.log(datetime.datetime.now(), '        ask        ', 'Timeout')
            self.logger.error('Timeout Error in function ask')
            try:
                self.sock.sendto(cmd, (self.host, self.port))
                data = self.sock.recv(size)
                self.Command = cmd + ': ' + str(data) + '\n'
                if data.startswith('?ERROR') or data.startswith('ERROR'):
                    self.logger.error(self.Command)
                return data
            except Exception, e:
                self.logger.error('Unknown error in function ask. %s', e)
                raise
            
        except socket.error, error:
            self.logger.error('Socket Error in function ask. %s',error)
            raise
        except Exception, e:
            self.logger.error('Unknown error in function ask. %s', e)
            raise

        finally:
            self.lock.release()

    def extractMultichannel(self, chain, initialpos):
        answersplit = chain.strip('\x00').split(' ')
        if answersplit[0] == '?MEAS' or answersplit[0] == '?LDATA':
            status = answersplit[len(answersplit) - 1]
            parameters = answersplit[initialpos:len(answersplit)-1]
        else:
            parameters = answersplit[initialpos:len(answersplit)]
        couples = []
        if len(parameters)%2 != 0:
            self.logger.error('Error in extractMultichannel. Parameters: %s', str(parameters))
            raise Exception('extractMultichannel: Wrong number of parameters')
        for i in range(0, len(parameters)/2):
            if parameters[i*2] in ['1', '2', '3', '4']:
                couples.append([parameters[i*2], parameters[i*2 + 1]])
            else: 
                self.logger.error('Error @extractMultichannel. Parameters: %s Command: %s', str(parameters), self.Command)
                raise Exception('extractMultichannel: Wrong channel')
        self.logger.debug("extractMultichannel:%s"%(couples))
        if answersplit[0] == '?MEAS':
            return couples, status
        elif answersplit[0] == '?LDATA' or answersplit[0].startswith('?DATA'):
            lastpos = answersplit[1]
            return couples, status, lastpos #@warning: WTF! where this lastpos comes from??
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
            self.logger.debug("getRanges: SEND: %s\t RCVD: %s"%(command, answer))
            ranges = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getRanges: %s"%(e))
            raise
        self.logger.debug("getRanges: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getRanges: %s"%(ranges))
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
            raise Exception("setRanges: %s"%(e))
        self.logger.debug("setRanges: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getEnables: %s"%(e))
            raise
        self.logger.debug("getEnables: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getEnables: %s"%(enables))
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
            self.logger.error("setEnables: %s"%(e))
        self.logger.debug("setEnables: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getInvs: %s"%(e))
            raise
        self.logger.debug("getInvs: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getInvs: %s"%(invs))
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
            self.logger.error("setInvs: %s"%(e))
        self.logger.debug("setInvs: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getFilters: %s"%(e))
            raise
        self.logger.debug("getFilters: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getFilters: %s"%(filters))
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
            self.logger.error("setFilters: %s"%(e))
        self.logger.debug("setFilters: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getOffsets: %s"%(e))
            raise
        self.logger.debug("getOffsets: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getOffsets: %s"%(offsets))
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
            self.logger.error("setOffsets: %s"%(e))
        self.logger.debug("setOffsets: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getAmpmodes: %s"%(e))
            raise
        self.logger.debug("getAmpmodes: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getAmpmodes: %s"%(ampmodes))
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
            self.logger.error("setAmpmodes: %s"%(e))
        self.logger.debug("setAmpmodes: SEND: %s\t RCVD: %s"%(command, answer))

    def setAmpmodes(self, ampmodes):
        self.StopAdc()
        self._setAmpmodes(ampmodes)
        self.StartAdc()

    def setAmpmodesAll(self, ampmode):
        self.StopAdc()
        self.setAmpmodes([['1', ampmode], ['2', ampmode], ['3', ampmode], ['4', ampmode]])

    def getLdata(self):
        
        try:
            command = '?LDATA'
            answer = self.ask(command)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                lastpos = 0
                measures = []
                status = ''
        except Exception, e:
            self.logger.error("getLdata: %s"%(e))
            raise
        self.logger.debug("getLdata: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getLdata: %s, %s %s"%(measures, status, lastpos))
        return measures, status, lastpos

    def getData(self, position):
        try:
            command = '?DATA %s'%position
            answer = self.ask(command)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                lastpos = 0
                measures = ''
                status = ''
        except Exception, e:
            self.logger.error("getData: %s"%(e))
            raise
        self.logger.debug("getLdata: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getLdata: %s, %s"%(measures, status, lastpos))
        return measures, status, lastpos
        
    
    def getLastpos(self):
        measures, status, lastpos = self.getLdata()
        return lastpos

    def getBuffer(self):
        lastpos = self.getLastpos()
        thebuffer = []
        for i in range(0, lastpos):
            measures, status, lastpos = self.getData(i) #getLdata() bug included by Mr. JLidon
            thebuffer.append([float(measures[0][1]), float(measures[1][1]), float(measures[2][1]), float(measures[3][1])])
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
            measures, status = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getMeasures: %s"%(e))
            raise
        self.logger.debug("getMeasures: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getMeasures: %s, %s"%(measures, status))
        return measures, status

    def getMeasure(self, channel):
        try:
            command = '?MEAS'
            answer = self.ask(command)
            measure, status = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getMeasure: %s"%(e))
            raise
        self.logger.debug("getMeasure: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getMeasure: %s, %s"%(measure, status))
        self.logger.debug("getMeasure: %s"%(measure[int(channel[0])-1][1]))
        return measure[int(channel[0])-1][1]

    def getMeasuresAll(self):
        return self.getMeasures(['1', '2', '3', '4'])

    def getAvsamples(self):
        try:
            command = '?AVSAMPLES'
            answer = self.ask(command)
            avsamples = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getAvsamples: %s"%(e))
            raise
        self.logger.debug("getAvsamples: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getAvsamples: %s"%(avsamples))
        return avsamples

    def _setAvsamples(self, avsamples):
        try: 
            command = 'AVSAMPLES %s'%(avsamples)
            answer = self.ask(command)
            if answer != 'AVSAMPLES ACK\x00':
                raise Exception('setAvsamples: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setAvsamples: %s"%(e))
            self.logger.error("setAvsamples: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("setAvsamples: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getPoints: %s"%(e))
            raise
        self.logger.debug("getPoints: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getPoints: %s"%(points))
        return points

    def _setPoints(self, points):
        try: 
            command = 'POINTS %s'%(points)
            answer = self.ask(command)
            if answer != 'POINTS ACK\x00':
                raise Exception('setPoints: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setPoints: %s"%(e))
        #self.logger.debug("setPoints: SEND: %s\t RCVD: %s"%(command, answer))

    def setPoints(self, points):
        self.StopAdc()
        self._setPoints(points)
        self.StartAdc()

    def getTrigperiod(self):
        try:
            command = '?TRIGPERIODE'
            self.logger.debug('getTrigperiod: Sending command...')
            answer = self.ask(command)
            trigperiode = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getTrigperiod: %s"%(e))
            raise
        self.logger.debug("getTrigperiod: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getTrigperiod: %s"%(trigperiode))
        return trigperiode

    def _setTrigperiod(self, trigperiod):
        try: 
            command = 'TRIGPERIODE %s'%(trigperiod)
            answer = self.ask(command)
            if answer != 'TRIGPERIODE ACK\x00':
                raise Exception('setTrigperiod: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setTrigperiod: %s"%(e))
        self.logger.debug("setTrigperiod: SEND: %s\t RCVD: %s"%(command, answer))

    def setTrigperiod(self, trigperiod):
        self.StopAdc()
        self._setTrigperiod(trigperiod)
        self.StartAdc()

    def getTrigmode(self):
        try:
            command = '?TRIGMODE'
            self.logger.debug('getTrigmode: Sending command...')
            answer = self.ask(command)
            trigmode = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getTrigmode: %s"%(e))
            raise
        self.logger.debug("getTrigmode: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getTrigmode: %s"%(trigmode))
        return trigmode

    def _setTrigmode(self, trigmode):
        try: 
            command = 'TRIGMODE %s'%(trigmode)
            answer = self.ask(command)
            if answer != 'TRIGMODE ACK\x00':
                raise Exception('setTrigmode: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setTrigmode: %s"%(e))
        self.logger.debug( "setTrigmode: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getSrate: %s"%(e))
            raise
        self.logger.debug("getSrate: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getSrate: %s"%(srate))
        return srate

    def _setSrate(self, srate):
        try: 
            command = 'SRATE %s'%(srate)
            answer = self.ask(command)
            if answer != 'SRATE ACK\x00':
                raise Exception('setSrate: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setSrate: %s"%(e))
        self.logger.debug("setSrate: SEND: %s\t RCVD: %s"%(command, answer))

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
            self.logger.error("getState: %s"%(e))
            raise
        self.logger.debug("getState: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getState: %s"%(state))
        return state

    def getStatus(self):
        try:
            command = '?STATUS'
            answer = self.ask(command)
            status = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getStatus: %s"%(e))
            raise
        self.logger.debug("getStatus: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getStatus: %s"%(status))
        return status

    def getMode(self):
        try:
            command = '?MODE'
            answer = self.ask(command)
            mode = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getMode: %s"%(e))
            raise
        self.logger.debug("getMode: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getMode: %s"%(mode))
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
            self.logger.error("Start: %s"%(e))
        #self.logger.debug("Start: SEND: %s\t RCVD: %s"%(command, answer))

    def StartAdc(self):
        try: 
            command = 'STARTADC'
            answer = self.ask(command)
            if answer != 'STARTADC ACK\x00':
                raise Exception('StartAdc: Wrong acknowledge')
        except Exception, e:
            self.logger.error("StartAdc: %s"%(e))
        #self.logger.debug("StartAdc: SEND: %s\t RCVD: %s"%(command, answer))

    def StopAdc(self):
        try: 
            command = 'STOPADC'
            answer = self.ask(command)
            if answer != 'STOPADC ACK\x00':
                raise Exception('StopAdc: Wrong acknowledge')
        except Exception, e:
            self.logger.error("StopAdc: %s"%(e))
        #self.logger.debug("StopAdc: SEND: %s\t RCVD: %s"%(command, answer))

    def Stop(self):
        try: 
            command = 'STOP'
            answer = self.ask(command)
            if answer != 'STOP ACK\x00':
                raise Exception('Stop: Wrong acknowledge')
        except Exception, e:
            self.logger.error("Stop: %s"%(e))
        self.logger.debug("Stop: SEND: %s\t RCVD: %s"%(command, answer))

    def sendSetCmd(self, cmd):
        self.StopAdc()
        self.ask(cmd)
        self.StartAdc()    

    def clearOffsetCorr(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        self.StopAdc()
        for r in ranges:
            self.ask('OFFSETCORR %s 1 0 2 0 3 0 4 0'%r)
        self.StartAdc()

    def getOffsetCorrAll(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for r in ranges:
            self.logger.debug(self.ask('?OFFSETCORR %s'%r))

    def getGainCorrAll(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for r in ranges:
            self.logger.debug(self.ask('?GAINCORR %s'%r))

    def resetGainCorr(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for r in ranges:
            self.logger.debug(self.sendSetCmd('GAINCORR %s %s 1'%(r, channel)))

    def resetOffsetCorr(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        for r in ranges:
            self.logger.debug(self.sendSetCmd('OFFSETCORR %s %s 0'%(r, channel)))

    def toggleGainCorrPolarisation(self, channel):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        gaincorrs = []
        for r in ranges:
            gaincorr = self.ask('?GAINCORR %s'%r).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        self.logger.debug("Initial gaincorr factors:")
        for gc in gaincorrs:
            print gc
        self.StopAdc()
        for r in ranges:
            self.ask('GAINCORR %s %s %s'%(r, channel, -1*float(gaincorrs[ranges.index(r)][2+2*int(channel)-1])))
        self.StartAdc()
        gaincorrs = []
        for r in ranges:
            gaincorr = self.ask('?GAINCORR %s'%r).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        self.logger.debug("Final gaincorr factors:")
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
        self.logger.debug("Loading config to EM:")
        for c in cmd:
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
        for r in ranges:
            mystring = self.ask('?OFFSETCORR %s'%r).strip('\x00').split(' ')
            mylogstring.append("OFFSETCORR,%s,%s,%s,%s,%s\n"%(r, mystring[3], mystring[5], mystring[7], mystring[9]))
        for r in ranges:
            mystring = self.ask('?GAINCORR %s'%r).strip('\x00').split(' ')
            mylogstring.append("GAINCORR,%s,%s,%s,%s,%s\n"%(r, mystring[3], mystring[5], mystring[7], mystring[9]))
        return mylogstring

    def dumpConfig(self, dumpfile):
        mylogstring = self._dumpConfig()
        myfile = open(dumpfile, 'w') 
        self.logger.debug("Dumping config to file: %s"%dumpfile)
        for line in mylogstring:
            self.logger.debug(line.strip('\n'))
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
        self.logger.debug("Comparing config of em %s with dumpfile %s..."%(self.host, dumpfile))
        for i in range(0, len(mylogstring)):
            if mylogstring[i] != mydumpedstring[i]:
                self.logger.debug("Current config and dumped config missmatch:")
                self.logger.debug("Current: %s"%mylogstring[i].strip('\n'))
                self.logger.debug("Dump file: %s"%mydumpedstring[i].strip('\n'))
                missmatches = missmatches + 1
        self.logger.debug("Comparison finished. Number of missmatches:%s"%missmatches)

    def checkAgainstDefaultDumpedConfig(self):
        self.checkAgainstDumpedConfig('./%s.dump'%self.host)

        

if __name__ == "__main__":
    # TWO BASIC PARAMETERS, unit address and channel 
    #Substitute ask by ask2 in order to use savechain method for debugging without hw
    
    DftLogFormat = '%(threadName)-14s %(levelname)-8s %(asctime)s %(name)s: %(message)s'
    #logging.basicConfig(filename='filenameforlogs.log',format=DftLogFormat)
    format = logging.Formatter(DftLogFormat)
    handler = logging.handlers.RotatingFileHandler('LibTestingErrors', maxBytes=10240, backupCount=5)
    handler.setFormatter(format)
    myalbaem = albaem('elem01r42-013-bl13.cells.es')
    myalbaem.logger.addHandler(handler)
    
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
    
    myalbaem.dumpDefaultConfig()
    myalbaem.checkAgainstDefaultDumpedConfig()
    myalbaem.loadDefaultConfig()
    '''
    
    #myalbaem.getState()
    myalbaem.setPoints(1)
    myalbaem.Start()
    #myalbaem.getState()
    myalbaem.getLdata()
