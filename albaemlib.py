
import time
import array
from scipy.stats import *
import socket
#import datetime
#import logging
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

class AlbaEm():
    '''
        This is the main library used for the communications with Alba electrometers.
        The configuration of the serial line is: 8bits + 1 stopbit, bdr: 9600, terminator:none
        The cable is crossed
     '''

    def __init__(self, host, logFileName='AlbaEmLog.log', port=7, record=True):
        #self.logger = AlbaEmLogger(logFileName,record)
        #DftLogFormat = '%(threadName)-14s %(levelname)-8s %(asctime)s %(name)s: %(message)s'
        #logging.basicConfig(filename=logFileName,format=DftLogFormat,level=logging.DEBUG)
        
        self.logger = logging.Logger("albaEmLIB")
        self.logger.setLevel(logging.INFO)
        
        self.host = host
        self.port = port
        self.lock = Lock()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #@deprecated: it seems not useful nevermore.
        self.sock.settimeout(0.3)
        self.offset_corr_alarm = False
        self.saturation_list = 'List:'
        self.stateMoving = False
        

    def ask(self, cmd, size=8192):
        '''
            Basic method for send commands to the Alba Electrometer.
            @param cmd: Command for send to electrometer.
            @param size: Default value is 8192. This param is the maximum
                            amount of data to be received at once.
            @return: Data received from Alba electrometer.
        ''' 
        try:
            #@todo: wait until \x00 has arrived as answer.
            
            self.lock.acquire()
            self.sock.sendto(cmd, (self.host, self.port))
            data = ''
            while not data.endswith('\x00'):
                answer = self.sock.recv(size)
                data = data + answer
            self.Command = cmd + ': ' + str(data) + '\n'
            
            if data.startswith('?ERROR') or data.startswith('ERROR'):
                self.logger.debug('Command: %s Data: %s' ,cmd,data)
                
            elif not data.startswith(cmd.split()[0]):
                self.logger.debug('Command: %s Data: %s' ,cmd,data)
                #@todo: should be raise an exception?
                raise socket.timeout
            else:
                self.logger.debug('AlbaEM DEBUG: query:',cmd,'\t','answer length:', len(data), '\t', 'answer:#%s#'%(data))
                return data
         
        except socket.timeout, timeout:
            self.logger.error('Timeout Error in method ask sending the command: %s', cmd)
            try:
                #@deprecated: There is no need to send the command again.
                #self.sock.sendto(cmd, (self.host, self.port))
                timesToCheck = 50
                data = ''
                while timesToCheck > 0:
                    timesToCheck -= 1
                    while not data.endswith('\x00'):
                        answer = self.sock.recv(size)
                        data = data + answer
                    self.Command = cmd + ': ' + str(data) + '\n'
                    if data.startswith('?ERROR') or data.startswith('ERROR'):
                        self.logger.error('Error reading the command %s again after a timeout', self.Command)
                        raise Exception('Error reading the command %s again after a timeout'%self.Command)
                    elif not data.startswith(cmd.split()[0]):
                        self.logger.debug('Command: %s Data: %s' ,cmd,data)
                        raise Exception('Error reading the command %s again after a timeout'%self.Command)
                    else:
                        return data
            except Exception, e:
                self.logger.error('Unknown error in method ask. %s', e)
                raise
            
        except socket.error, error:
            self.logger.error('Socket Error in method ask/sending the command: %s. Error: %s' %(self.Command,error))
            raise
        except Exception, e:
            self.logger.error('Unknown error in method ask/sending the command: %s. Error: %s' %(self.Command,e))
            raise

        finally:
            self.lock.release()

    def extractMultichannel(self, chain, initialpos):
        '''
            This method cleans the answer from alba electrometer and 
            returns only the important data. 
            @param chain: String to extract the useful data.
            @param initialpos: initial position of the string with useful data.
            
            @return: Useful data obtained from the albaem answer.
        '''
        answersplit = chain.strip('\x00').split(' ')
        if answersplit[0] == '?MEAS' or answersplit[0] == '?IINST' or answersplit[0] == '?LDATA' or answersplit[0] == '?DATA':
            status = answersplit[len(answersplit) - 1]
            parameters = answersplit[initialpos:len(answersplit)-1]
        else:
            parameters = answersplit[initialpos:len(answersplit)]
            
        if answersplit[0] == '?AVDATA':
            return map(float,parameters)
        couples = []
        if len(parameters)%2 != 0:
            self.logger.error('Error @extractMultichannel. Parameters: %s Command: %s', str(parameters), self.Command)
            raise Exception('extractMultichannel: Wrong number of parameters')
        for i in range(0, len(parameters)/2):
            if parameters[i*2] in ['1', '2', '3', '4']:
                couples.append([parameters[i*2], parameters[i*2 + 1]])
            else: 
                self.logger.error('Error @extractMultichannel. Parameters: %s Command: %s', str(parameters), self.Command)
                raise Exception('extractMultichannel: Wrong channel')
        self.logger.debug("extractMultichannel:%s"%(couples))
        if answersplit[0] == '?MEAS' or answersplit[0] == '?IINST':
            return couples, status
        elif answersplit[0] == '?LDATA' or answersplit[0].startswith('?DATA'):
            lastpos = answersplit[1]
            return couples, status, lastpos 
        else: 
            return couples

    def extractSimple(self, chain):
        '''
            Do the same than extractMultichannel but it is used when the answer 
            from electrometer is only one word.
            @param chain: String to extract the useful data.
            
            @return: Useful data obtained from the albaem answer.
        '''
        data = chain.strip('\x00').split(' ')[1]
        return data

    def _getChannelsFromList(self, channels):
        """
            Method to receive the channels as a list of integers 
            and transform it to a string to add to the command to send.
            @param channels: List of channels to add to the command.
            
            @return: string with the channels
        """
        channelChain = ''
        for channel in channels:
            channelChain ='%s %s '%(channelChain, channel)
        return channelChain
    
    def _prepareChannelsAndValues(self, valuesAndChannelsList):
        """
            Method to receive the channels as a list of integers 
            and transform it to a string to add to the command to send.
            @param channels: List of channels to add to the command.
            
            @return: string with the channels
        """
        channelChain = ''
        for couple in valuesAndChannelsList:
            channelChain = '%s %s %s'%(channelChain, couple[0], couple[1])
            
        return channelChain


    def getAutoRangeMin(self, channels):
        """
            Method to get the autoRangeMin for each channel.
            @param channels: List of channels to obtain the data.
            
            @return: list of channels and autoranges
        """
        
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?AUTORANGEMIN %s'%channelChain
            answer = self.ask(command)
            self.logger.debug("getAutoRangeMin: SEND: %s\t RCVD: %s"%(command, answer))
            autoRangeMin = self.extractMultichannel(answer, 1)
        
        except Exception, e:
            self.logger.error('getAutoRangeMin: %s' %e)
            raise
        self.logger.debug("getAutoRangeMin: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getAutoRangeMin: %s"%(autoRangeMin))
        return autoRangeMin
    
    def getAllAutoRangesMin(self):
        """
            Method for getting the autorangeMin of each channel.
            @return: State of autorangeMin
        """
        return self.getAutoRangeMin(['1', '2', '3', '4'])

    def _setAutoRangeMin(self, autoRangesMin):
        """
        """
        channelChain = self._prepareChannelsAndValues(autoRangesMin)
        answer = None
        try:
            command = 'AUTORANGEMIN %s' %channelChain
            answer = self.ask(command)
            
            if answer != 'AUTORANGEMIN ACK\x00':
                raise Exception('setAutoRangesMin: Wrong acknowledge')
        except Exception, e:
            raise Exception('setAutoRangesMin: %s' %e)
        self.logger.debug('setAutoRangesMin: SEND: %s\t RCVD: %s' %(command, answer))
    
    def setAutoRangeMin(self, autoRangeMin):
        """
            Method to set the autoRangeMin for each channel in the list.
            @param autoRangeMin: List of channels and values
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRangeMin(autoRangeMin)
        self.StartAdc()
    
    def setAllAutoRangesMin(self, autoRangeMin):
        """
            Method to set the autoRangeMin for all channels.
            @param autoRangesMin in %
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRangeMin([['1', autoRangeMin], ['2', autoRangeMin], ['3', autoRangeMin], ['4', autoRangeMin]])
        self.StartAdc()


    def getAutoRangeMax(self, channels):
        """
            Method to get the autoRangeMax for each channel.
            @param channels: List of channels to obtain the data.
            
            @return: list of channels and autoranges
        """
        
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?AUTORANGEMAX %s'%channelChain
            answer = self.ask(command)
            self.logger.debug("getAutoRangeMax: SEND: %s\t RCVD: %s"%(command, answer))
            autoRangeMax = self.extractMultichannel(answer, 1)
        
        except Exception, e:
            self.logger.error('getAutoRangeMax: %s' %e)
            raise
        self.logger.debug("getAutoRangeMax: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getAutoRangeMax: %s"%(autoRangeMax))
        return autoRangeMax
    
    def getAllAutoRangesMax(self):
        """
            Method for getting the autorangeMax of each channel.
            @return: State of autorangeMax
        """
        return self.getAutoRangeMax(['1', '2', '3', '4'])

    def _setAutoRangeMax(self, autoRangesMax):
        """
        """
        channelChain = self._prepareChannelsAndValues(autoRangesMax)
        answer = None
        try:
            command = 'AUTORANGEMAX %s' %channelChain
            answer = self.ask(command)
            
            if answer != 'AUTORANGEMAX ACK\x00':
                raise Exception('setAllAutoRangesMax: Wrong acknowledge')
        except Exception, e:
            raise Exception('setAllAutoRangesMax: %s' %e)
        self.logger.debug('setAllAutoRangesMax: SEND: %s\t RCVD: %s' %(command, answer))
    
    def setAutoRangeMax(self, autoRangeMax):
        """
            Method to set the autoRangeMax for each channel in the list.
            @param autoRangeMax: List of channels and values
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRangeMax(autoRangeMax)
        self.StartAdc()
    
    def setAllAutoRangesMax(self, autoRangeMax):
        """
            Method to set the autoRangeMax for all channels.
            @param autoRangesMax in % 
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRangeMax([['1', autoRangeMax], ['2', autoRangeMax], ['3', autoRangeMax], ['4', autoRangeMax]])
        self.StartAdc()




    def getAutoRange(self, channels):
        """
            Method to get the autoRange for each channel.
            @param channels: List of channels to obtain the data.
            
            @return: list of channels and autoranges
        """
        
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?AUTORANGE %s'%channelChain
            answer = self.ask(command)
            self.logger.debug("getAutoRange: SEND: %s\t RCVD: %s"%(command, answer))
            autoRange = self.extractMultichannel(answer, 1)
        
        except Exception, e:
            self.logger.error('getAutoRanges: %s' %e)
            raise
        self.logger.debug("getAutoRanges: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getAutoRanges: %s"%(autoRange))
        return autoRange
    
    def getAllAutoRanges(self):
        """
            Method for getting the autorange of each channel.
            @return: State of autorange 
        """
        return self.getAutoRange(['1', '2', '3', '4'])

    def _setAutoRange(self, autoRanges):
        """
        """
        channelChain = self._prepareChannelsAndValues(autoRanges)
        answer = None
        try:
            command = 'AUTORANGE %s' %channelChain
            answer = self.ask(command)
            
            if answer != 'AUTORANGE ACK\x00':
                raise Exception('setAllAutoRanges: Wrong acknowledge')
        except Exception, e:
            raise Exception('setAllAutoRanges: %s' %e)
        self.logger.debug('setAllAutoRanges: SEND: %s\t RCVD: %s' %(command, answer))
    
    def setAutoRange(self, autoRange):
        """
            Method to set the autoRange for each channel in the list.
            @param autoRangeEnables: List of channels and values
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRange(autoRange)
        self.StartAdc()
    
    def setAllAutoRanges(self, autoRange):
        """
            Method to set the autoRange for all channels.
            @param autoRanges: {YES | NO}
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAutoRange([['1', autoRange], ['2', autoRange], ['3', autoRange], ['4', autoRange]])
        self.StartAdc()

    
    def getRanges(self, channels):
        '''
            Method for read the range in a channel.
            @param channels: List of channels to obtain the range.
            
            @return: List of ranges.
        '''
        
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?RANGE %s'%channelChain
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
        '''
            Method for read all the ranges.
            @return: List of ranges.
        '''
        return self.getAutoRange(['1', '2', '3', '4'])

    def _setRanges(self, ranges):
        '''
            Method for set Ranges.
            @param ranges: list of ranges to set.
        '''
        answer = None
        channelChain = self._prepareChannelsAndValues(ranges)
        try: 
            command = 'RANGE %s'%(channelChain)
            answer = self.ask(command)
            if answer != 'RANGE ACK\x00':
                raise Exception('setRanges: Wrong acknowledge')
        except Exception, e:
            raise Exception("setRanges: %s"%(e))
        self.logger.debug("setRanges: SEND: %s\t RCVD: %s"%(command, answer))

    def setRanges(self, ranges):
        """
            Method used for setting the ranges of each channel.
            @param ranges: List of channels and values to set.
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setRanges(ranges)
        self.StartAdc()

    def setRangesAll(self, range):
        """
            This Method set all the channels with the same values.
            @param range: Range to apply in all the channels.
        """
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.setRanges([['1', range], ['2', range], ['3', range], ['4', range]])
        self.StartAdc()

    def getEnables(self, channels):
        """
            Method to get the enables of each channel.
            @param channels: List of channels to get the enables.
            @return: list of enables.
        """
        
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?ENABLE %s'%channelChain
            answer = self.ask(command)
            enables = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getEnables: %s"%(e))
            raise
        self.logger.debug("getEnables: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getEnables: %s"%(enables))
        return enables

    def getEnablesAll(self):
        """
            Method to get the enables of all channels.
            @return: list of enables.
        """
        return self.getEnables(['1', '2', '3', '4'])

    def _setEnables(self, enables):
        
        channelChain = self._prepareChannelsAndValues(enables)    
        answer = None
        try: 
            command = 'ENABLE %s'%(channelChain)
            answer = self.ask(command)
            if answer != 'ENABLE ACK\x00':
                raise Exception('setEnables: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setEnables: %s"%(e))
        self.logger.debug("setEnables: SEND: %s\t RCVD: %s"%(command, answer))

    def setEnables(self, enables):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setEnables(enables)
        self.StartAdc()

    def setEnablesAll(self, enable):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()        
        self.StopAdc()
        self.setEnables([['1', enable], ['2', enable], ['3', enable], ['4', enable]])
        self.StartAdc()

    def disableAll(self):
        self.setEnables([['1', 'NO'],['2', 'NO'],['3', 'NO'],['4', 'NO']])

    def enableChannel(self, channel):
        self.setEnables([['%s'%channel, 'YES']])

    def getInvs(self, channels):
            
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?INV %s'%channelChain
            answer = self.ask(command)
            invs = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getInvs: %s"%(e))
            raise
        self.logger.debug("getInvs: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getInvs: %s"%(invs))
        return invs

    def getDInvs(self, channels):
        dinvs = []
        answer = None
        try:
            for channel in channels:
                command = '?GAINCORR 1mA %s'%channel
                answer = self.ask(command)
                self.logger.debug(answer)
                val = float((answer.split(' ')[3].strip('\00')))
                self.logger.debug(answer, val)
                if val < 0:
                    res = 'YES'
                else:
                    res = 'NO'
                dinvs.append([channel, res])
        except Exception, e:
            self.logger.error("getDInvs: %s"%(e))
            raise
        self.logger.debug("getDInvs: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getDInvs: %s"%(dinvs))
        return dinvs

    def getDInvsAll(self):
        return self.getDInvs(['1', '2', '3', '4'])

    def getInvsAll(self):
        return self.getInvs(['1', '2', '3', '4'])

    def _setInvs(self, invs):

        channelChain = self._prepareChannelsAndValues(invs)
        answer = None
        try: 
            command = 'INV %s'%(channelChain)
            answer = self.ask(command)
            if answer != 'INV ACK\x00':
                raise Exception('setInvs: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setInvs: %s"%(e))
        self.logger.debug("setInvs: SEND: %s\t RCVD: %s"%(command, answer))

    def _setDInvs(self, dinvs):
        for couple in dinvs:
            if couple[1] == 'YES':
                self.toggleGainCorrPolarisation(int(couple[0]), factor = -1, relative = 0)
            else:
                self.toggleGainCorrPolarisation(int(couple[0]), factor = 1, relative = 0)
 
    def setDInvs(self, dinvs):
        '''
            @param dinvs: [['1','YES'|'NO'],...,['4','YES'|'NO']]
        '''
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setDInvs(dinvs)

    def setDInvsAll(self, dinv):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.setDInvs([['1', dinv], ['2', dinv], ['3', dinv], ['4', dinv]])
        self.StartAdc()

    def setInvs(self, invs):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setInvs(invs)
        self.StartAdc()

    def setInvsAll(self, inv):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.setInvs([['1', inv], ['2', inv], ['3', inv], ['4', inv]])
        self.StartAdc()

    def getFilters(self, channels):
            
        channelChain = self._getChannelsFromList(channels)    
        answer = None
        try:
            command = '?FILTER %s'%channelChain
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
            
        channelChain = self._prepareChannelsAndValues(filters)
        answer = None
        try: 
            command = 'FILTER %s'%(channelChain)
            print "COMMAND: ", command
            answer = self.ask(command)
            if answer != 'FILTER ACK\x00':
                raise Exception('setFilters: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setFilters: %s"%(e))
        self.logger.debug("setFilters: SEND: %s\t RCVD: %s"%(command, answer))

    def setFilters(self, filters):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setFilters(filters)
        self.StartAdc()

    def setFiltersAll(self, filter):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.setFilters([['1', filter], ['2', filter], ['3', filter], ['4', filter]])
        self.StartAdc()

    def getOffsets(self, channels):
                    
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?OFFSET %s'%channelChain
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
            
        channelChain = self._prepareChannelsAndValues(offsets)
        answer = None
        try: 
            command = 'OFFSET %s'%(channelChain)
            answer = self.ask(command)
            if answer != 'OFFSET ACK\x00':
                raise Exception('setOffsets: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setOffsets: %s"%(e))
        self.logger.debug("setOffsets: SEND: %s\t RCVD: %s"%(command, answer))

    def setOffsets(self, offsets):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setOffsets(offsets)
        self.StartAdc()

    def setOffsetsAll(self, offset):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.setOffsets([['1', offset], ['2', offset], ['3', offset], ['4', offset]])
        self.StartAdc()

    def getAmpmodes(self, channels):

        channelChain = self._getChannelsFromList(channels)    
        answer = None
        try:
            command = '?AMPMODE %s'%channelChain
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

    def _setAmpmodes(self, ampModes):
        channelChain = ''
        for couple in ampModes:
            channelChain = '%s %s %s '%(channelChain, couple[0], couple[1])
            
        channelChain = self._prepareChannelsAndValues(ampModes)
        answer = None
        try: 
            command = 'AMPMODE %s'%(channelChain)
            answer = self.ask(command)
            if answer != 'AMPMODE ACK\x00':
                raise Exception('setAmpmodes: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setAmpmodes: %s"%(e))
        self.logger.debug("setAmpmodes: SEND: %s\t RCVD: %s"%(command, answer))

    def setAmpmodes(self, ampmodes):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAmpmodes(ampmodes)
        self.StartAdc()

    def setAmpmodesAll(self, ampmode):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
#        self.StopAdc()
        self.setAmpmodes([['1', ampmode], ['2', ampmode], ['3', ampmode], ['4', ampmode]])

    def getLdata(self):
        answer = None
        try:
            command = '?LDATA'
            answer = self.ask(command)
            self.logger.info(answer)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                self.logger.debug('BUFFER ERROR!')
                raise Exception('BUFFER ERROR in getLData!')
                #lastpos = 0
                #measures = []
                #status = ''
        except Exception, e:
            self.logger.error("getLdata: %s"%(e))
            raise
        self.logger.debug("getLdata: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getLdata: %s, %s %s"%(measures, status, lastpos))
        return measures, status, lastpos

    def getData(self, position):
        answer = None
        try:
            command = '?DATA %s'%position
            answer = self.ask(command)
            if not answer.startswith('?BUFFER ERROR'):
                measures, status, lastpos = self.extractMultichannel(answer, 2)
                lastpos = int(lastpos) + 1 #We use 0 for the case when no data is available
            else:
                self.logger.debug('BUFFER ERROR!')
                raise Exception('BUFFER ERROR in getLData!')
                #lastpos = 0
                #measures = ''
                #status = ''
        except Exception, e:
            self.logger.error("getData: %s"%(e))
            raise
        self.logger.debug("getData: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getData: %s, %s, %s"%(measures, status, lastpos))
        return measures, status, lastpos
        
    
    def getLastpos(self):
        measures, status, lastpos = self.getLdata()
        return lastpos

    def getAvData(self, channel):
        buffer = []
        answer = None
        try:
            command = '?AVDATA %s'%channel
            answer = self.ask(command)
            if not answer.startswith('?BUFFER ERROR'):
                buffer = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getAvData: %s"%(e))
            raise
        self.logger.debug('getAvData: SEND:%s\t RCVD: %s'%(command, answer))
        self.logger.debug('getAvData: %s'%buffer)
        return buffer
    
    #Deprecated -------------------------------    
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
    # -------------------------------
    
    def _digitalOffsetCorrect(self, chans, rang, digitaloffsettarget, correct = 1):
        print "Correcting channels, range, digitaloffsettarget:", chans, rang, digitaloffsettarget
        cmd = []
        for ch in chans:
            cmd.append(['%s'%ch, rang])
        #self.logger.debug(cmd)
        print(cmd)
        self.setRanges(cmd)
        time.sleep(2)
        measures = self.ask('?VMEAS').strip('\x00').split(' ')
        #self.logger.debug('%s %s  %s  %s  %s'%(rang, measures[2], measures[4], measures[6], measures[8]))
        print('%s %s  %s  %s  %s'%(rang, measures[2], measures[4], measures[6], measures[8]))
        
        measures2 = [float(measures[2]), float(measures[4]), float(measures[6]), float(measures[8])]
        measures3 = []
        for i in range(0, len(measures2)): 
            measures3.append(-measures2[i] + digitaloffsettarget)
        #self.logger.debug(measures3)
        print measures3
        cmdpar = ''
        for i in chans:
            cmdpar = cmdpar + ' %s %s'%(i, measures3[i-1])
        print cmdpar
        print 'Correction command:OFFSETCORR %s%s'%(rang, cmdpar)
        if correct == 1:
            self.sendSetCmd('OFFSETCORR %s%s'%(rang, cmdpar))
        
    def digitalOffsetCorrect(self, chans, ranges='all', digitaloffsettarget=0, correct = 1):
        self.stateMoving=True
        oldAvsamples = self.getAvsamples()
        self.setAvsamples(1000)
        self.saturation_list = "List: "

        if ranges == 'all':
            ranges = ['100pA', '1nA', '10nA', '100nA', '1uA', '10uA', '100uA', '1mA']
        digitaloffsettarget = (10.0)*digitaloffsettarget
        for rang in ranges:
            self._digitalOffsetCorrect(chans, rang, digitaloffsettarget, correct)
        self.setAvsamples(oldAvsamples)
        self.offset_corr_alarm = False
        self.stateMoving=False
        for ran in ranges:
            offsetcorr_all = self.getOffsetCorrAll()
            line = offsetcorr_all.get(ran)
            for l in line:
                ch = float(l[1])
                if -10.<= ch >= 10.:
                    self.offset_corr_alarm = True
                    self.saturation_list = self.saturation_list + repr(l)
                    print "Channel",l[0],"range:",ran,"Saturado, valor",l[1]
        print "Status of OffsetCorrAlarm: ", self.offset_corr_alarm


    def digitalOffsetCheck(self):
        self.digitalOffsetCorrect([1,2,3,4], correct = 0)

    def configDiagnose(self, chan):
        self.logger.debug('ConfigDiagnose initiating configuration ...')
        self.getInfo()
        self.setAvsamples(1)
        self.setTrigperiod(1)
        self.setPoints(1000)
        self.setTrigmode('INT')
        self.logger.debug('Acquiring ...')
        self.Start()
        time.sleep(2)
        mydata = self.getBufferChannel(chan)
        return mydata
        
    def getInstantMeasures(self, channels):
            
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?IINST %s'%channelChain
            answer = self.ask(command)
            measures, status = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getInstantMeasures: %s"%(e))
            raise
        self.logger.debug("getInstantMeasures: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getInstantMeasures: %s, %s"%(measures, status))
        return measures, status

    def getInstantMeasure(self, channel):
        answer = None
        try:
            command = '?IINST'
            answer = self.ask(command)
            measure, status = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getInstantMeasure: %s"%(e))
            raise
        self.logger.debug("getInstantMeasure: SEND: %s\t RCVD: %s"%(command, answer))
        #self.logger.debug("getInstantMeasure: %s, %s"%(measure, status))
        self.logger.debug("getInstantMeasure: %s"%(measure[int(channel[0])-1][1]))
        return measure[int(channel[0])-1][1]
        #return measure, status

    def getInstantMeasuresAll(self):
        return self.getInstantMeasures(['1', '2', '3', '4'])
        
    def getMeasures(self, channels):
            
        channelChain = self._getChannelsFromList(channels)
        answer = None
        try:
            command = '?MEAS %s'%channelChain
            answer = self.ask(command)
            measures, status = self.extractMultichannel(answer, 1)
        except Exception, e:
            self.logger.error("getMeasures: %s"%(e))
            raise
        self.logger.debug("getMeasures: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getMeasures: %s, %s"%(measures, status))
        return measures, status

    def getMeasure(self, channel):
        answer = None
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
        answer = None
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
        answer = None
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
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setAvsamples(avsamples)
        self.StartAdc()

    def getPoints(self):
        answer = None
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
        answer = None
        try: 
            command = 'POINTS %s'%(points)
            answer = self.ask(command)
            if answer != 'POINTS ACK\x00':
                raise Exception('setPoints: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setPoints: %s"%(e))
        #self.logger.debug("setPoints: SEND: %s\t RCVD: %s"%(command, answer))

    def setPoints(self, points):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setPoints(points)
        self.StartAdc()
        
    def getTrigDelay(self):
        answer = None
        try:
            command = '?TRIGDELAY'
            self.logger.debug('getTrigDelay: Sending command...')
            answer = self.ask(command)
            trigperiode = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getTrigDelay: %s"%(e))
            raise
        self.logger.debug("getTrigDelay: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getTrigDelay: %s"%(trigperiode))
        return trigperiode

    def _setTrigDelay(self, delay):
        answer = None
        try: 
            command = 'TRIGDELAY %s'%(delay)
            answer = self.ask(command)
            if answer != 'TRIGDELAY ACK\x00':
                raise Exception('setTrigDelay: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setTrigDelay: %s"%(e))
        self.logger.debug("setTrigDelay: SEND: %s\t RCVD: %s"%(command, answer))

    def setTrigDelay(self, delay):
        '''This method changes the delay of each trigger
           @param delay: delay in ms.
        '''
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setTrigDelay(delay)
        self.StartAdc()

    def getTrigperiod(self):
        answer = None
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
        answer = None
        try: 
            command = 'TRIGPERIODE %s'%(trigperiod)
            answer = self.ask(command)
            if answer != 'TRIGPERIODE ACK\x00':
                raise Exception('setTrigperiod: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setTrigperiod: %s"%(e))
        self.logger.debug("setTrigperiod: SEND: %s\t RCVD: %s"%(command, answer))

    def setTrigperiod(self, trigperiod):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setTrigperiod(trigperiod)
        self.StartAdc()

    def getTrigmode(self):
        answer = None
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
        answer = None
        try: 
            command = 'TRIGMODE %s'%(trigmode)
            answer = self.ask(command)
            if answer != 'TRIGMODE ACK\x00':
                raise Exception('setTrigmode: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setTrigmode: %s"%(e))
        self.logger.debug( "setTrigmode: SEND: %s\t RCVD: %s"%(command, answer))

    def setTrigmode(self, trigmode):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setTrigmode(trigmode)
        self.StartAdc()

    def getSrate(self):
        answer = None
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
        answer = None
        try: 
            command = 'SRATE %s'%(srate)
            answer = self.ask(command)
            if answer != 'SRATE ACK\x00':
                raise Exception('setSrate: Wrong acknowledge')
        except Exception, e:
            self.logger.error("setSrate: %s"%(e))
        self.logger.debug("setSrate: SEND: %s\t RCVD: %s"%(command, answer))

    def setSrate(self, srate):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self._setSrate(srate)
        self.StartAdc()

    def getState(self):
        answer = None
        try:
            command = '?STATE'
            answer = self.ask(command)
            state = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getState: %s"%(e))
            raise
        self.logger.debug("getState: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getState: %s"%(state))
        if self.offset_corr_alarm == True:
            state = "ALARM"
        if self.stateMoving == True:
            state = "MOVING"
        return state

    def getStatus(self):
        answer = None
        try:
            command = '?STATUS'
            answer = self.ask(command)
            status = self.extractSimple(answer)
        except Exception, e:
            self.logger.error("getStatus: %s"%(e))
            raise
        self.logger.debug("getStatus: SEND: %s\t RCVD: %s"%(command, answer))
        self.logger.debug("getStatus: %s"%(status))
        print "offset_corr_alarm:", self.offset_corr_alarm
        if self.offset_corr_alarm == True:
            status = "Current input detected is too high for offset correction for the following" + self.saturation_list + " <channels/range>.\nPlease verify that channel is unconnected before proceeding with the offset correction"
        return status

    def getMode(self):
        answer = None
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
        answer = None
        try: 
            command = 'START'
            answer = self.ask(command)
            if answer != 'START ACK\x00':
                raise Exception('Start: Wrong acknowledge')
        except Exception, e:
            self.logger.error("Start: %s"%(e))
        #self.logger.debug("Start: SEND: %s\t RCVD: %s"%(command, answer))

    def StartAdc(self):
        answer = None
        try: 
            command = 'STARTADC'
            answer = self.ask(command)
            if answer != 'STARTADC ACK\x00':
                raise Exception('StartAdc: Wrong acknowledge')
        except Exception, e:
            self.logger.error("StartAdc: %s"%(e))
        #self.logger.debug("StartAdc: SEND: %s\t RCVD: %s"%(command, answer))

    def StopAdc(self):
        answer = None
        try: 
            command = 'STOPADC'
            answer = self.ask(command)
            if answer != 'STOPADC ACK\x00':
                raise Exception('StopAdc: Wrong acknowledge')
        except Exception, e:
            self.logger.error("StopAdc: %s"%(e))
        #self.logger.debug("StopAdc: SEND: %s\t RCVD: %s"%(command, answer))

    def Stop(self):
        answer = None
        try: 
            command = 'STOP'
            answer = self.ask(command)
            if answer != 'STOP ACK\x00':
                raise Exception('Stop: Wrong acknowledge')
        except Exception, e:
            self.logger.error("Stop: %s"%(e))
        self.logger.debug("Stop: SEND: %s\t RCVD: %s"%(command, answer))

    def sendSetCmd(self, cmd):
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        self.ask(cmd)
        self.StartAdc()    

    def clearOffsetCorr(self):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        self.StopAdc()
        for r in ranges:
            self.ask('OFFSETCORR %s 1 0 2 0 3 0 4 0'%r)
        self.StartAdc()

    def getOffsetCorr(self,range, channel):
        '''
            @param range: Range to use.
            @param channel: channel to use. Starting in 1
            @return: Offset for the channel 
        '''
        offset = self.ask('?OFFSETCORR %s 1 2 3 4' %range)
        offsets = self.extractMultichannel(offset, 2)
        return offsets[channel-1][1]
    
    def getOffsetCorrAll(self):
        '''
            Get offsets for each range and return a dictionary with an entrance
            for each range.
        '''
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        offsets = {}
        answer = None
        for r in ranges:
            command = '?OFFSETCORR %s' % r
            answer = self.ask(command)
            offsets[r] = self.extractMultichannel(answer, 2)
            self.logger.debug("Stop: SEND: %s\t RCVD: %s"%(command, answer))
        return offsets
    
    
    

    def _setOffsetCorrect(self, rang,  chans):   
        '''
            Is called from setOffsetCorrect, 
            @chans is a list os values and chanels
            @rang is a String of range.
        '''
        s=" "
        for o in chans:
            for i in o:
                s += '%s ' % i
        print 'Sending command:OFFSETCORR %s%s'%(rang, s)
        #if correct == 1:
        self.sendSetCmd('OFFSETCORR %s%s'%(rang, s))
      
      
    def setOffsetCorrect(self, values):
        '''
            @chans - Diccionary of Channel and values
            @ranges - List of Ranges to loop
        '''
        for val in values:
            self._setOffsetCorrect(val, values.get(val))
       


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

    def toggleGainCorrPolarisation(self, channel, factor = -1, relative = 1):
        ranges = ['1mA', '100uA', '10uA', '1uA', '100nA', '10nA', '1nA', '100pA']
        gaincorrs = []
        for r in ranges:
            gaincorr = self.ask('?GAINCORR %s'%r).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        self.logger.debug("Initial gaincorr factors:")
        for gc in gaincorrs:
            self.logger.debug(gc)
        state = self.getState()
        if state == 'RUNNING':
            self.Stop()
        self.StopAdc()
        print 'Channels: %s'%channel
        print 'gaincor: %s'%gaincorr
        if relative == 1:
            for r in ranges:
                self.ask('GAINCORR %s %s %s'%(r, channel, factor*int(float(gaincorrs[ranges.index(r)][2+2*int(channel)-1]))))
                time.sleep(0.2)
        else:
            for r in ranges:
                self.ask('GAINCORR %s %s %s'%(r, channel, factor*abs(int(float(gaincorrs[ranges.index(r)][2+2*int(channel)-1])))))
                #time.sleep(0.2)
            
        self.StartAdc()
        gaincorrs = []
        for r in ranges:
            gaincorr = self.ask('?GAINCORR %s'%r).strip('\n').strip('\00').split(' ')
            gaincorrs.append(gaincorr)
        self.logger.debug("Final gaincorr factors:")
        for gc in gaincorrs:
            self.logger.debug(gc)
    
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
    myFormat = logging.Formatter(DftLogFormat)
    handler = logging.handlers.RotatingFileHandler('LibTestingErrors', maxBytes=10240, backupCount=5)
    handler.setFormatter(myFormat)
    myalbaem = AlbaEm('elem01r42s009')
    myalbaem.logger.addHandler(handler)
    
    
#    emu = False
#    print myalbaem.getRangesAll()
#    print myalbaem.setRangesAll('1mA')
#    print myalbaem.getRangesAll()
#    print myalbaem.setRangesAll('100uA')
#    print myalbaem.getRangesAll()
#    print myalbaem.getFiltersAll()
#    print myalbaem.setFiltersAll('NO')
#    print myalbaem.getFiltersAll()
#    print myalbaem.setFiltersAll('10')
#    print myalbaem.getFiltersAll()
#    print myalbaem.getInvsAll()
#    print myalbaem.setInvsAll('NO')
#    print myalbaem.getInvsAll()
#    print myalbaem.setInvsAll('YES')
#    print myalbaem.getInvsAll()
#    print myalbaem.getOffsetsAll()
#    print myalbaem.getEnablesAll()
#    print myalbaem.getAmpmodesAll()
#    print myalbaem.setAmpmodesAll('HB')
#    print myalbaem.getAmpmodesAll()
#    print myalbaem.setAmpmodesAll('LN')
#    print myalbaem.getAmpmodesAll()
#    print myalbaem.getAvsamples()
#    print myalbaem.getTrigperiod()
#    print myalbaem.getPoints()
#    myalbaem.dumpEM('./em.dump')
#    myalbaem.loadEM('./em.dump')
#    
#    myalbaem.dumpDefaultConfig()
#    myalbaem.checkAgainstDefaultDumpedConfig()
#    myalbaem.loadDefaultConfig()
#    
#    
#    myalbaem.getState()
#    myalbaem.setPoints(2)
#    myalbaem.Start()
#    #myalbaem.getState()
#
#    import time
##    time.sleep(1)
##    #data = myalbaem.getData(1)
##    data = myalbaem.getBuffer()
##    print data[0]
##    print data[1]
##    chan = myalbaem.getBufferChannel(1)
##    print chan
##    print type(chan[0])
#    #myalbaem.getLdata()
#    rdata = myalbaem.ask('?RAWDATA 1')
#    print rdata
#    print len(rdata)
#
#    
#    print '---- Getting all autoranges ----'
#    print myalbaem.getAutoRange(['1'])
#    print myalbaem.getAutoRange(['1','2'])
#    print myalbaem.getAutoRange(['1','2','3'])
#    print myalbaem.getAutoRange(['1','2','3','4'])
#    print myalbaem.getAllAutoRanges()
#    
#    print '---- Setting all autoranges ----'
#    myalbaem.setAllAutoRanges('YES')
#    print myalbaem.getAllAutoRanges()
#    
#    myalbaem.setAutoRange([['1','YES']])
#    print myalbaem.getAllAutoRanges()
#    
#    myalbaem.setAutoRange([['2','YES']])
#    print myalbaem.getAllAutoRanges()
#    
#    myalbaem.setAutoRange([['3','YES']])
#    print myalbaem.getAllAutoRanges()
#    
#    myalbaem.setAutoRange([['4','YES']])
#    print myalbaem.getAllAutoRanges()
#    
#    myalbaem.setAutoRange([['2','NO'],['3','NO']])
#    print myalbaem.getAllAutoRanges()
#    myalbaem.setAutoRange([['2','YES'],['3','NO'],['4','NO']])
#    print myalbaem.getAllAutoRanges()
#    myalbaem.setAutoRange([['1','NO'],['2','NO'],['3','NO'],['4','NO']])
#    print myalbaem.getAllAutoRanges()
    
#    print '---- Getting all instant measures ----'
#    print myalbaem.getMeasures([1,2,3,4])
#    print myalbaem.getInstantMeasuresAll()
#    
#    print '---- Getting instant measures ----'
#    print myalbaem.getInstantMeasure('1')
#    print myalbaem.getInstantMeasure('2')
#    print myalbaem.getInstantMeasure('3')
#    print myalbaem.getInstantMeasure('4')
#    print myalbaem.getInstantMeasures([2])
#    print myalbaem.getInstantMeasures(['1','2'])
#    print myalbaem.getInstantMeasures([1,2,3])
#    print myalbaem.getInstantMeasures([1,2,3,4])
    
#    print '---- Changing trigger delay ----'
#    print myalbaem.getTrigDelay()
#    print myalbaem.setTrigDelay(100)
#    print myalbaem.getTrigDelay()
#    print myalbaem.setTrigDelay(0)
#    print myalbaem.getTrigDelay()


#    print '---- Getting all autorangesMin ----'
#    print myalbaem.getAutoRangeMin(['1'])
#    print myalbaem.getAutoRangeMin(['1','2'])
#    print myalbaem.getAutoRangeMin(['1','2','3'])
#    print myalbaem.getAutoRangeMin(['1','2','3','4'])
#    print myalbaem.getAllAutoRangesMin()
#    
#    print '---- Getting all autorangesMax ----'
#    print myalbaem.getAutoRangeMax(['1'])
#    print myalbaem.getAutoRangeMax(['1','2'])
#    print myalbaem.getAutoRangeMax(['1','2','3'])
#    print myalbaem.getAutoRangeMax(['1','2','3','4'])
#    print myalbaem.getAllAutoRangesMax()
#    
#    print '---- Setting all autorangesMin ----'
#    #myalbaem.setAllAutoRangesMin('20')
#    #print myalbaem.getAllAutoRangesMin()
#    
#    myalbaem.setAutoRangeMin([['1','15']])
#    print myalbaem.getAllAutoRangesMin()
#    
#    myalbaem.setAutoRangeMin([['2','15']])
#    print myalbaem.getAllAutoRangesMin()
#    
#    myalbaem.setAutoRangeMin([['3','15']])
#    print myalbaem.getAllAutoRangesMin()
#    
#    myalbaem.setAutoRangeMin([['4','15']])
#    print myalbaem.getAllAutoRangesMin()
#    
##    myalbaem.setAutoRangeMin([['2',10],['3',10]])
##    print myalbaem.getAllAutoRangesMin()
##    myalbaem.setAutoRangeMin([['2',5],['3',5],['4',5]])
##    print myalbaem.getAllAutoRangesMin()
##    myalbaem.setAutoRangeMin([['1',5],['2',5],['3',5],['4',5]])
##    print myalbaem.getAllAutoRangesMin()
#    
#    print '---- Setting all autorangesMax ----'
##    myalbaem.setAllAutoRangesMax('80')
##    print myalbaem.getAllAutoRangesMax()
#    
#    myalbaem.setAutoRangeMax([['1',90]])
#    print myalbaem.getAllAutoRangesMax()
#    
#    myalbaem.setAutoRangeMax([['2','85']])
#    print myalbaem.getAllAutoRangesMax()
#    
#    myalbaem.setAutoRangeMax([['3','85']])
#    print myalbaem.getAllAutoRangesMax()
#    
#    myalbaem.setAutoRangeMax([['4','85']])
#    print myalbaem.getAllAutoRangesMax()
#    
#    myalbaem.setAutoRangeMax([['2',95],['3',95]])
#    print myalbaem.getAllAutoRangesMax()
#    myalbaem.setAutoRangeMax([['2',95],['3',95],['4',95]])
#    print myalbaem.getAllAutoRangesMax()
#    myalbaem.setAutoRangeMax([['1',95],['2',95],['3',95],['4',95]])
#    print myalbaem.getAllAutoRangesMax()
    
    



