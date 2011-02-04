#!/usr/bin/env python
#################################################################
# python fitbit object
# By Kyle Machulis <kyle@nonpolynomial.com>
# http://www.nonpolynomial.com
#
# Distributed as part of the libfitbit project
#
# Repo: http://www.github.com/openyou/libfitbit
#
# Licensed under the BSD License, as follows
#
# Copyright (c) 2011, Kyle Machulis/Nonpolynomial Labs
# All rights reserved.
#
# Redistribution and use in source and binary forms, 
# with or without modification, are permitted provided 
# that the following conditions are met:
#
#    * Redistributions of source code must retain the 
#      above copyright notice, this list of conditions 
#      and the following disclaimer.
#    * Redistributions in binary form must reproduce the 
#      above copyright notice, this list of conditions and 
#      the following disclaimer in the documentation and/or 
#      other materials provided with the distribution.
#    * Neither the name of the Nonpolynomial Labs nor the names 
#      of its contributors may be used to endorse or promote 
#      products derived from this software without specific 
#      prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND 
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
# MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT 
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; 
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#################################################################
#
# ANT code originally taken from
# http://code.google.com/p/mstump-learning-exercises/source/browse/trunk/python/ANT/ant_twisted.py
# Added to and untwistedized and basically fixed up by Kyle Machulis <kyle@nonpolynomial.com>
#
# What's Done
#
# - Basic ANT protocol implementation
# - Basic FitBit protocol implementation
# - FitBit Base Initialization
# - FitBit Tracker Connection, Initialization, Info Retreival
# - Blind data retrieval (can get it, don't know what it is)
#
# To Do (Big)
#
# - Talking to the fitbit website
# - Dividing out into modules (ant classes may become their own library)
# - Figuring out more data formats and packets
# - Implementing data clearing
# - Fix ANT Burst packet identifer
# - Add checksum checks for ANT receive
# - Fix packet status identifiers in ANT

import itertools
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

class ANTReceiveException(Exception):
    pass

class ANT(object):

    def __init__(self, chan=0x00, debug=False):
        self._debug = debug
        self._chan = chan

        self._state = 0
        self._transmitBuffer = []
        self._receiveBuffer = []

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
        data = self._receive()
        print ["%02x" % (x) for x in data]
        if data[2] == 0x6f:
            return
        raise ANTStatusException("Reset expects message type 0x6f, got %02x" % (data[2]))

    def _check_ok_response(self):
        # response packets will always be 7 bytes
        status = self._receive()

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

    def receive_acknowledged_reply(self, size = 13):        
        while 1:
            status = self._receive()
            if len(status) > 0 and status[2] == 0x4F:
                return status[4:-1].tolist()

    def _check_acknowledged_response(self):
        # response packets will always be 7 bytes
        while 1:
            status = self._receive()
            if len(status) > 0 and status[2] == 0x40 and status[5] == 0x5:
                break

    def _check_burst_response(self):
        response = []
        failure = False
        while 1:
            try:
                status = self._receive(15)
            except ANTReceiveException:
                failure = True
            if len(status) > 0 and status[2] == 0x50 or status[2] == 0x4f:
                response = response + status[4:-1].tolist()
                if status[3] == 0xc0 or status[3] == 0xe0 or status[3] == 0xa0 or status[2] == 0x4f:
                    if failure:
                        raise ANTReceiveException("Burst receive failed!")
                    return response

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
        self._transmitBuffer = map(chr, array.array('B', data + [reduce(operator.xor, data)]))

        if self._debug:
            print "--> " + hexRepr(self._transmitBuffer)
        return self._send(self._transmitBuffer)

    def _receive(self, size=4096):
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
        self.timeout = 1000

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
        self._connection.write(self.ep['out'], map(ord, c), 0, 100)

    def _receive(self, size=4096):
        r = self._connection.read(self.ep['in'], size, 0, self.timeout)
        checksum = reduce(operator.xor, r[:-1])
        if len(r) == 0 or checksum != r[-1]:
            raise ANTReceiveException("Checksums for packet do not match received values!")
        if self._debug:
            self.data_received(''.join(map(chr, r)))
        return r


class FitBit(ANTlibusb):

    class FitBitTracker(object):
        def __init__(self):
            # Cycle of 0-8, for creating tracker packet serial numbers
            self.tracker_packet_count = itertools.cycle(range(0,8))

            # The tracker expects to start on 1, i.e. 0x39 This is set
            # after a reset (which is why we create the tracker in the
            # reset function). It won't talk if you try anything else.
            self.tracker_packet_count.next()

            self.current_bank_id = 1
            self.current_packet_id = None
            self.serial = None
            self.firmware_version = None
            self.bsl_major_version = None
            self.bsl_minor_version = None
            self.app_major_version = None
            self.app_minor_version = None
            self.in_mode_bsl = None
            self.on_charger = None

        def get_packet_id(self):
            self.current_packet_id = 0x38 + self.tracker_packet_count.next()
            return self.current_packet_id

        def parse_info_packet(self, data):
            self.serial = data[0:5]
            self.firmware_version = data[5]
            self.bsl_major_version = data[6]
            self.bsl_minor_version = data[7]
            self.app_major_version = data[8]
            self.app_minor_version = data[9]
            self.in_mode_bsl = (False, True)[data[10]]
            self.on_charger = (False, True)[data[11]]

        def __str__(self):
            return "Tracker Serial: %s\n" \
                "Firmware Version: %d\n" \
                "BSL Version: %d.%d\n" \
                "APP Version: %d.%d\n" \
                "In Mode BSL? %s\n" \
                "On Charger? %s\n" % \
                ("".join(["%x" % (x) for x in self.serial]),
                 self.firmware_version,
                 self.bsl_major_version,
                 self.bsl_minor_version,
                 self.app_major_version,
                 self.app_minor_version,
                 self.in_mode_bsl,
                 self.on_charger)

    def __init__(self, debug = False):
        super(FitBit, self).__init__(debug=debug)
        self.tracker = None

    def open(self):
        return super(FitBit, self).open(0x10c4, 0x84c4)

    def fitbit_control_init(self):
        # Device setup
        # bmRequestType, bmRequest, wValue, wIndex, data
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        # # At this point, we get a 4096 buffer, then start all over
        # # again? Apparently doesn't require an explicit receive
        self._connection.ctrl_transfer(0x40, 0x00, 0x0, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x00, 0xFFFF, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x2000, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x01, 0x4A, 0x0, [])
        # # Receive 1 byte, should be 0x2
        self._connection.ctrl_transfer(0xC0, 0xFF, 0x370B, 0x0, 1)
        self._connection.ctrl_transfer(0x40, 0x03, 0x800, 0x0, [])
        self._connection.ctrl_transfer(0x40, 0x13, 0x0, 0x0, \
                                           [0x08, 0x00, 0x00, 0x00,
                                            0x40, 0x00, 0x00, 0x00,
                                            0x00, 0x00, 0x00, 0x00,
                                            0x00, 0x00, 0x00, 0x00
                                            ])
        self._connection.ctrl_transfer(0x40, 0x12, 0x0C, 0x0, [])
        try:
            self._receive()
        except usb.USBError:
            pass


        # We get an ant reset message after doing all of this, that
        # I'm going to guess means we're connected and running. Not
        # seeing it in the USB analyzer logs, but whatever.
        # self._check_reset_response()

    def reset_tracker(self):
        # 0x78 0x01 is apparently the device reset command
        self.send_acknowledged_data([0x78, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def init_tracker_for_transfer(self):
        # 0x78 0x02 is device id reset. This tells the device the new
        cid = [random.randint(0,254), random.randint(0,254)]
        self.send_acknowledged_data([0x78, 0x02] + cid + [0x00, 0x00, 0x00, 0x00])
        self.close_channel()
        self.init_device_channel(cid + [0x01, 0x01])
        self.wait_for_beacon()
        self.tracker = self.FitBitTracker()
        
    def wait_for_beacon(self):
        # FitBit device initialization
        while 1:
            try:
                d = self._receive()
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

        self.init_device_channel([0xff, 0xff, 0x01, 0x01])
        
    def _get_tracker_burst(self):
        d = self._check_burst_response()
        if d[1] != 0x81:
            raise Exception("Response received is not tracker burst! Got %s" % (d[0:2]))
        size = d[3] << 8 | d[2]
        if size == 0:
            return []
        return d[8:8+size]

    def send_tracker_control_packet(self, index):
        self.send_tracker_packet([0x70, 0x00, 0x02, index, 0x00, 0x00, 0x00])
        return self._get_tracker_burst()

    def get_tracker_info(self):
        # Device data retrieval
        self.tracker.parse_info_packet(self.send_tracker_control_packet(0x0))
        print self.tracker

    def send_tracker_packet(self, packet, expected_response = None):
        self.send_acknowledged_data([self.tracker.get_packet_id()] + packet)
        if expected_response is not None:
            self.check_tracker_response(expected_response)

    def check_tracker_response(self, response):
        data = self.receive_acknowledged_reply()
        if data[0] != self.tracker.current_packet_id:
            raise Exception("Tracker Packet IDs don't match! %s %s", (data[0], self.tracker.current_packet_id))
        if data[1:] != response:
            raise Exception("Tracker Packet responses don't match! %s %s", (data[1:], response))

    def ping_tracker(self):
        self.send_acknowledged_data([0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def check_tracker_data_bank(self, index):
        self.send_tracker_packet([0x60, 0x00, 0x02, index, 0x00, 0x00, 0x00])
        return self._get_tracker_burst()

    def get_data_bank(self, index, stride):        
        self.send_tracker_packet([0x22, index, 0x00, 0x00, 0x00, 0x00, 0x00])
        data = []
        while 1:
            try:
                bank = self.check_tracker_data_bank(self.tracker.current_bank_id)
            except ANTReceiveException:
                continue
            self.tracker.current_bank_id += 1
            if len(bank) == 0:
                for i in range(0, len(data), stride):
                    print ["%02x" %(x) for x in data[i:i+stride]]
                return data
            data = data + bank                
        
    def transfer(self):
        # Goal of the transfer function: None of these should be
        # "send_tracker_packet" calls. Everything should be named what
        # it actually is.
        
        # This is a replay of commands taken from the windows client
        # logs.

        # URL REQUEST HERE
        # This is where we get the first opcode for pinging

        # Ping Command
        self.ping_tracker()
        self.send_tracker_packet([0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
                                 [0x42, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

        # Get tracker info starts us at 0x0. Each call increases by
        # one, be it to a databank or a configuration query.
        self.get_tracker_info()

        # The rules after we pick up the tracker info get a little
        # freaky. This ignores the beginning increasing index byte,
        # we're just talking about commands here.
        #
        # First off, we send an opcode, from the array listed below

        opcode_array = [0x05, 0x04, 0x02, 0x00, 0x01]
                   
        # Opcode should return us a status like
        #
        # 0x42
        #
        # After which, we send what I guess is the "databank opener"
        # command.
        #
        # 0x70 0x00 0x02 0x0X
        #
        # (THIS MAY NOT BE RIGHT. I'm seeing opcodes followed by 0x60
        # commands in the log.)
        #
        # The X is a databank index, starting from 0 (which it
        # actually does back in our get_tracker_info function, but we
        # have that hardcoded since we actually know what that data
        # is.) X increases by 1 with every command
        #
        # This should get us back at least some data. We then continue
        # emptying the databank using the "databank continue" commands
        #
        # 0x60 0x00 0x02 0x0X
        # 
        # Once we hit a bank with no data, we send the next
        # opcode. Repeat until we're out of opcodes.
        #
        # So, the whole loop looks like:
        #
        # --> 0x22 0x05 - Opcode
        # <-- 0x01 0x05 - Success
        # <-- 0x42 - Opcode Success? 
        # --> 0x70 0x00 0x02 0x02 - 0x70 command? MAY NOT BE RIGHT
        # <-- 0x01 0x05
        # <-- 0x81 [length] [lots of packets]
        # --> 0x60 0x00 0x02 0x03 - 0x60 continuation command? 
        # <-- 0x01 0x05
        # <-- 0x81 0x0 - We're out of data, start the next opcode.
        # --> 0x22 0x04
        # etc...

        self.get_data_bank(0x05, 1000)
        self.get_data_bank(0x04, 1000)
        self.get_data_bank(0x02, 13)
        self.get_data_bank(0x00, 7)
        self.get_data_bank(0x01, 14)

        # for opcode in opcode_array:
        #     self.get_data_bank(opcode)

        # URL REQUEST HERE
        # This is where we ship everything back to the mothership

        # somewhere down here, we would erase data. If only we knew how.

    def run_transfer(self):
        self._connection.reset()
        self.init_fitbit()
        self.wait_for_beacon()
        self.reset_tracker()
        self.init_tracker_for_transfer()
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
