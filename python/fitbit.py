#!/usr/bin/env python

# Originally taken from
# http://code.google.com/p/mstump-learning-exercises/source/browse/trunk/python/ANT/ant_twisted.py
# Added to and untwistedized by Kyle Machulis <kyle@nonpolynomial.com>

import time
import base64
import sys
import operator
import struct
import array
import usb
import random

def hexList(data):
    return map(lambda s: s.encode('HEX'), data)

def hexRepr(data):
    return repr(hexList(data))

def intListToByteList(data):
    return map(lambda i: struct.pack('!H', i)[1], array.array('B', data))

class ANTStatusException(Exception):
    pass

class ANT(object):

    def __init__(self, chan=0x00, debug=False):
        self._debug = debug
        self._chan = chan

        self._state = 0
        self._transmitBuffer = []
        self._receiveBuffer = []
        self._old_output = []

    def data_received(self, data):
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
                    printBuffer.append(self._event_to_string(message[4]))
                    printBuffer.extend(hexList(intListToByteList(message[5:-1])))
                    printBuffer.append("CHKSUM:%02x" % message[-1])
                    # if message[4] == 1:
                        # reactor.callLater(self._messageDelay, self.opench)
                else:
                    printBuffer = hexRepr(intListToByteList(message))

                # print "<-- " + repr(printBuffer)

    def _event_to_string(self, event):
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

    def _check_reset_response(self):
        data = self._receive(5)
        if data[2] == 0x6f:
            self._old_output = data
            return
        raise ANTStatusException("Reset expects message type 0x6f, got %02x" % (data[2]))

    def _check_ok_response(self):
        # response packets will always be 7 bytes
        status = self._receive(7)
        
        if status[2] == 0x40 and status[5] == 0x0:
            return
        
        raise ANTStatusException("Message status %d does not match 0x0 (NO_ERROR)" % (status[5]))

    def reset(self):
        self._send_message(0x4a, 0x00)
        self._check_reset_response()

    def set_channel_frequency(self, freq):
        self._send_message(0x45, self._chan, freq)
        self._check_ok_response()

    def set_transmit_power(self, power):
        self._send_message(0x47, 0x0, power)
        self._check_ok_response()

    def set_search_timeout(self, timeout):
        self._send_message(0x44, self._chan, timeout)
        self._check_ok_response()

    def send_network_key(self, network, key):
        self._send_message(0x46, network, key)
        self._check_ok_response()

    def set_channel_period(self, period):
        self._send_message(0x43, self._chan, period)
        self._check_ok_response()

    def set_channel_id(self, id):
        self._send_message(0x51, self._chan, id)
        self._check_ok_response()

    def open_channel(self):
        self._send_message(0x4b, self._chan)
        self._check_ok_response()

    def close_channel(self):
        self._send_message(0x4c, self._chan)
        self._check_ok_response()

    def assign_channel(self):
        self._send_message(0x42, self._chan, 0x00, 0x00)
        self._check_ok_response()

    def _check_acknowledged_response(self):
        # response packets will always be 7 bytes
        while 1:
            status = self._receive(4096, True)
            if len(status) > 0 and status[2] == 0x40 and status[5] == 0x5:
                if self._debug:
                    self.data_received(''.join(map(chr, status)))
                break
            #time.sleep(1)

    def _check_burst_response(self):
        # response packets will always be 7 bytes
        while 1:
            status = self._receive(4096, True)
            if len(status) > 0 and status[2] == 0x50:
                if self._debug:
                    self.data_received(''.join(map(chr, status)))
                if status[3] == 0xc0 or status[3] == 0xe0 or status[3] == 0xa0:
                    return 0

    def send_acknowledged_data(self, l):
        self._send_message(0x4f, self._chan, l)        
        self._check_acknowledged_response()

    def send_str(self, instring):
        if len(instring) > 8:
            raise "string is too big"

        return self._send_message(*[0x4e] + list(struct.unpack('%sB' % len(instring), instring)))

    def _send_message(self, *args):
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

    def _receive(self, size=64, quiet=False):
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

    def open(self, vid, pid):
        self._connection = usb.core.find(idVendor = vid,
                                         idProduct = pid)
        if self._connection is None:
            return False

        self._connection.set_configuration()
        return True

    def close(self):
        if self._connection is not None:
            self._connection = None

    def _send(self, command):
        # libusb expects ordinals, it'll redo the conversion itself.
        c = command
        # if ord(c[2]) == 0x4f:
        #     c = c + ['\x00', '\x00']
        # print c
        self._connection.write(self.ep['out'], map(ord, c), 0, 100)

    def _receive(self, size=64, quiet=False):
        r = self._connection.read(self.ep['in'], size, 0, 1000)
        if self._debug and not quiet:
            self.data_received(''.join(map(chr, r)))
        return r

class FitBit(ANTlibusb):
    def __init__(self, debug = False):
        super(FitBit, self).__init__(debug=debug)

    def open(self):
        return super(FitBit, self).open(0x10c4, 0x84c4)

    def fitbit_control_init(self):
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

        # We get an ant reset message after doing all of this, that
        # I'm going to guess means we're connected and running. Not
        # seeing it in the USB analyzer logs, but whatever.
        self._check_reset_response()

    def reset_fitbit(self):
        # 0x78 0x01 is apparently the device reset command
        self.send_acknowledged_data([0x78, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

        # 0x78 0x02 is device id reset. This tells the device the new
        cid = [random.randint(0,254), random.randint(0,254)]
        self.send_acknowledged_data([0x78, 0x02] + cid + [0x00, 0x00, 0x00, 0x00])
        self.close_channel()
        self.init_device_channel(cid + [0x01, 0x01])
        self.wait_for_beacon()

    def wait_for_beacon(self):
        # FitBit device initialization
        while 1:
            try:
                d = self._receive(13)
                if d[2] == 0x4E:
                    break
            except usb.USBError:
                pass

    def init_device_channel(self, channel): 
        # ANT device initialization
        self.reset()
        self.send_network_key(0, [0,0,0,0,0,0,0,0])
        self.assign_channel()
        self.set_channel_period([0x0, 0x10])
        self.set_channel_frequency(0x2)
        self.set_transmit_power(0x3)
        self.set_search_timeout(0xFF)
        self.set_channel_id(channel)
        self.open_channel()

    def init_fitbit(self):
        self.fitbit_control_init()
        self.init_device_channel([0xff, 0xff, 0x01, 0x01])
        # Run a whole bunch of descriptor stuff. Not sure why, just
        # replaying what I see.
        self._connection.ctrl_transfer(0x80, 0x06, 0x0303, 0x00, 0x02)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0303, 0x00, 0x3c)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0200, 0x00, 0x20)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0300, 0x00, 0x01fe)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0301, 0x0409, 0x01fe)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0302, 0x0409, 0x01fe)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0303, 0x0409, 0x01fe)
        self._connection.ctrl_transfer(0x80, 0x06, 0x0302, 0x0409, 0x01fe)

    def transfer(self):
        self.send_acknowledged_data([0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x39, 0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3A, 0x70, 0x00, 0x02, 0x00, 0x00, 0x00, 0x00])
        # Static. Should equal:
        # ['a4', '09', '50', '00', '3a', '81', '0c', '00', '00', '00', '00', 'ea', 'a0']
        # ['a4', '09', '50', '20', '58', 'f7', '7a', '65', '51', '0a', '02', '17', '23']
        # ['a4', '09', '50', 'c0', '02', '17', '00', '01', '1e', '5f', '00', '00', '68']
        self._check_burst_response()
        self.send_acknowledged_data([0x3B, 0x60, 0x00, 0x02, 0x01, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3C, 0x22, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3D, 0x60, 0x00, 0x02, 0x02, 0x00, 0x00, 0x00])
        # Changes - does not match usb log!
        # ['a4', '09', '50', '00', '3d', '81', '0e', '00', '00', '00', '00', 'XX', 'XX']
        # ['a4', '09', '50', '20', 'XX', '00', 'XX', '00', 'XX', '00', 'XX', '00', 'XX']
        # ['a4', '09', '50', 'c0', '1e', '1e', 'XX', '10', '1e', '5f', '00', '00', 'XX']        
        self._check_burst_response()
        self.send_acknowledged_data([0x3E, 0x60, 0x00, 0x02, 0x03, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3F, 0x22, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x38, 0x60, 0x00, 0x02, 0x04, 0x00, 0x00, 0x00])
        self._check_burst_response()
        self.send_acknowledged_data([0x39, 0x60, 0x00, 0x02, 0x05, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3A, 0x22, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3B, 0x60, 0x00, 0x02, 0x06, 0x00, 0x00, 0x00])
        self._check_burst_response()
        self.send_acknowledged_data([0x3C, 0x60, 0x00, 0x02, 0x07, 0x00, 0x00, 0x00])
        self._check_burst_response()
        self.send_acknowledged_data([0x3D, 0x60, 0x00, 0x02, 0x08, 0x00, 0x00, 0x00])
        self._check_burst_response()
        self.send_acknowledged_data([0x3E, 0x60, 0x00, 0x02, 0x09, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3F, 0x22, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x38, 0x70, 0x00, 0x02, 0x0A, 0x00, 0x00, 0x00])
        self._check_burst_response()
        self.send_acknowledged_data([0x39, 0x60, 0x00, 0x02, 0x0B, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3A, 0x22, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.send_acknowledged_data([0x3B, 0x70, 0x00, 0x02, 0x0C, 0x00, 0x00, 0x00])
        self._check_burst_response()
        # self.send_acknowledged_data([0x3C, 0x60, 0x00, 0x02, 0x0D, 0x00, 0x00, 0x00])
        # self.send_acknowledged_data([0x3D, 0x26, 0xC3, 0x3B, 0x46, 0x4D, 0x00, 0x00])
        # self.send_acknowledged_data([0x3A, 0x23, 0x00, 0x0E, 0x00, 0x00, 0x00, 0x00])

    def run_transfer(self):
        self._connection.reset()
        self.init_fitbit()
        self.wait_for_beacon()
        self.reset_fitbit()
        self.transfer()

    def run_opcode(self, opcode):
        pass

def main():
    device = FitBit(True)
    if not device.open():
        print "No devices connected!"
        return 1
    try:
        device.run_transfer()
    finally:
        print "Closing!"
        device.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
