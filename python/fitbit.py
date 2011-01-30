#!/usr/bin/env python

# Originally taken from
# http://code.google.com/p/mstump-learning-exercises/source/browse/trunk/python/ANT/ant_twisted.py
# Added to and untwistedized by Kyle Machulis <kyle@nonpolynomial.com>

import base64
import sys
import operator
import struct
import array
import usb

def hexList(data):
    return map(lambda s: s.encode('HEX'), data)

def hexRepr(data):
    return repr(hexList(data))

def intListToByteList(data):
    return map(lambda i: struct.pack('!H', i)[1], array.array('B', data))

class ANT(object):

    def __init__(self, chan=0x00, debug=False):
        self._debug = debug
        self._chan = chan

        self._state = 0
        self._transmitBuffer = []
        self._receiveBuffer = []

    def dataReceived(self, data):
        if self._debug:
            print "<-- " + hexRepr(data)

        self._receiveBuffer.extend(list(struct.unpack('%sB' % len(data), data)))

        if len(self._receiveBuffer) > 1 and self._receiveBuffer[0] == 0xa4:
            messageSize = self._receiveBuffer[1]
            totalMessageSize = messageSize + 4

            if len(self._receiveBuffer) >= totalMessageSize:
                message = self._receiveBuffer[:totalMessageSize]
                self._receiveBuffer = self._receiveBuffer[totalMessageSize:]

                if reduce(operator.xor, message[:-1]) != message[-1]:
                    print "RCV CORRUPT MSG: %s" % hexRepr(intListToByteList(message))
                    return

                printBuffer = []
                if message[2] == 0x40:
                    printBuffer.append("MSG_RESPONSE_EVENT")
                    printBuffer.append("CHAN:%02x" % message[3])
                    printBuffer.append(self._eventToString(message[4]))
                    printBuffer.extend(hexList(intListToByteList(message[5:-1])))
                    printBuffer.append("CHKSUM:%02x" % message[-1])
                    # if message[4] == 1:
                        # reactor.callLater(self._messageDelay, self.opench)
                else:
                    printBuffer = hexRepr(intListToByteList(message))

                print "<-- " + repr(printBuffer)

    def _eventToString(self, event):
        try:
            return { 0:"RESPONSE_NO_ERROR",
                     1:"EVENT_RX_SEARCH_TIMEOUT",
                     2:"EVENT_RX_FAIL",
                     3:"EVENT_TX",
                     4:"EVENT_TRANSFER_RX_FAILED",
                     5:"EVENT_TRANSFER_TX_COMPLETED",
                     6:"EVENT_TRANSFER_TX_FAILED",
                     7:"EVENT_CHANNEL_CLOSED",
                     8:"EVENT_RX_FAIL_GO_TO_SEARCH",
                     9:"EVENT_CHANNEL_COLLISION",
                     10:"EVENT_TRANSFER_TX_START",
                     21:"CHANNEL_IN_WRONG_STATE",
                     22:"CHANNEL_NOT_OPENED",
                     24:"CHANNEL_ID_NOT_SET",
                     25:"CLOSE_ALL_CHANNELS",
                     31:"TRANSFER_IN_PROGRESS",
                     32:"TRANSFER_SEQUENCE_NUMBER_ERROR",
                     33:"TRANSFER_IN_ERROR",
                     40:"INVALID_MESSAGE",
                     41:"INVALID_NETWORK_NUMBER",
                     48:"INVALID_LIST_ID",
                     49:"INVALID_SCAN_TX_CHANNEL",
                     51:"INVALID_PARAMETER_PROVIDED",
                     53:"EVENT_QUE_OVERFLOW",
                     64:"NVM_FULL_ERROR",
                     65:"NVM_WRITE_ERROR",
                     66:"ASSIGN_CHANNEL_ID",
                     81:"SET_CHANNEL_ID",
                     0x4b:"OPEN_CHANNEL"}[event]
        except:
            return "%02x" % event

    def reset(self):
        return self._sendMessage(0x4a, [0x00])

    def setChannelFrequency(self, freq):
        return self._sendMessage(0x45, [freq])

    def setTransmitPower(self, power):
        return self._sendMessage(0x47, [power])

    def setSearchTimeout(self, timeout):
        return self._sendMessage(0x44, [timeout])

    def sendNetworkKey(self, network, key):
        return self._sendMessage(0x46, [network, key])

    def setChannelPeriod(self, period):
        return self._sendMessage(0x43, [period])

    def setChannelID(self):
        return self._sendMessage(0x51, [0x00, 0x00, 0x00, 0x00, 0x00])

    def openChannel(self):
        return self._sendMessage(0x4b, [0x00])

    def assignChannel(self):
        return self._sendMessage(0x42, [self._chan, 0x00, 0x00])

    def sendAck(self, l):
        return self._sendMessage(0x4f, l)

    def sendStr(self, instring):
        if len(instring) > 8:
            raise "string is too big"

        return self._sendMessage(*[0x4e] + list(struct.unpack('%sB' % len(instring), instring)))

    def _sendMessage(self, *args):
        data = list()
        for l in list(args):
            if isinstance(l, list):
                data = data + l
            else:
                data.append(l)
        data.insert(0, len(data) - 1)
        data.insert(0, 0xa4)
        # self._transmitBuffer = map(lambda i: struct.pack('!H', i)[1], array.array('B', data + [reduce(operator.xor, data)]))
        self._transmitBuffer = map(chr, array.array('B', data + [reduce(operator.xor, data)]))

        if self._debug:
            print "--> " + hexRepr(self._transmitBuffer)
        return self._send(self._transmitBuffer)

    def _receive(self, size=64):
        raise Exception("Need to define _receive function for ANT child class!")

    def _send(self):
        raise Exception("Need to define _send function for ANT child class!")

class ANTlibusb(ANT):
    ep = { 'in'  : 0x81, \
           'out' : 0x01
           }

    def __init__(self, chan=0x0, debug=False):
        super(ANTlibusb, self).__init__(chan, debug)
        self._connection = False

    def openDevice(self, vid, pid):
        self._connection = usb.core.find(idVendor = vid,
                                         idProduct = pid)
        if self._connection is None:
            return False
        self._connection.set_configuration()
        return True

    def closeDevice(self):
        if self._connection is not None:
            self._connection = None

    def _send(self, command):
        # libusb expects ordinals, it'll redo the conversion itself.
        self._connection.write(self.ep['out'], map(ord, command), 0, 100)
        print ["%02x" % (x) for x in self._receive(12)]

    def _receive(self, size=64):
        return self._connection.read(self.ep['in'], size, 0, 1000)

class FitBit(ANTlibusb):
    def __init__(self, debug = False):
        super(FitBit, self).__init__(debug=debug)

    def openDevice(self):
        return super(FitBit, self).openDevice(0x10c4, 0x84c4)

    def controlInit(self):
        # Device setup
        # bmRequestType, bmRequest, wValue, wIndex, data
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        # At this point, we get a 4096 buffer, then start all over
        # again? Apparently doesn't require an explicit receive
        self._connection.ctrl_transfer(0x40, 0x00, 0x0, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x4A, 0x0, [])
        # Receive 1 byte, should be 0x2
        self._connection.ctrl_transfer(0xC0, 0xFF, 0x370B, 0x0, 1)
        self._connection.ctrl_transfer(0x40, 0x03, 0x800, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x13, 0x0, 0x0, \
                                           [0x08, 0x00, 0x00, 0x00,
                                            0x40, 0x00, 0x00, 0x00,
                                            0x00, 0x00, 0x00, 0x00,
                                            0x00, 0x00, 0x00, 0x00
                                            ])
        self._connection.ctrl_transfer(0x40, 0x12, 0x0C, 0x0, [])

        # We get an ant message after doing all of this, that I'm
        # going to guess means we're connected and running. Not seeing
        # it in the USB analyzer logs, but whatever.
        self._receive(12)

    def initDevice(self):
        self._connection.reset()
        self.controlInit()
        # ANT device initialization

        self.reset()
        self.sendNetworkKey(0, [0,0,0,0,0,0,0,0])
        self.assignChannel()
        self.setChannelPeriod(0)
        self.setChannelFrequency(0)
        self.setTransmitPower(0)
        self.setSearchTimeout(0)
        self.setChannelID()
        self.openChannel()

    def runOpCode(self, opcode):
        pass

def main():
    device = FitBit(True)
    if not device.openDevice():
        print "No devices connected!"
        return 1
    device.initDevice()
    return 0

if __name__ == '__main__':
    sys.exit(main())
