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
# - Talking to the fitbit website
# - Fix ANT Burst packet identifer
# - Add checksum checks for ANT receive
# - Fix packet status identifiers in ANT
#
# To Do (Big)
#
# - Dividing out into modules (ant classes may become their own library)
# - Figuring out more data formats and packets
# - Implementing data clearing

import itertools, sys, random, operator, datetime
import usb
from antprotocol.protocol import ANTReceiveException
from antprotocol.libusb import ANTlibusb

class FitBit(ANTlibusb):

    class FitBitTracker(object):
        def __init__(self):
            # Cycle of 0-8, for creating tracker packet serial numbers
            self.tracker_packet_count = itertools.cycle(range(0,8))
            self.tracker_packet_count.next()
            # The tracker expects to start on 1, i.e. 0x39 This is set
            # after a reset (which is why we create the tracker in the
            # reset function). It won't talk if you try anything else.
            # self.tracker_packet_count.next()

            self.current_bank_id = 0
            self.current_packet_id = None
            self.serial = None
            self.firmware_version = None
            self.bsl_major_version = None
            self.bsl_minor_version = None
            self.app_major_version = None
            self.app_minor_version = None
            self.in_mode_bsl = None
            self.on_charger = None

        def gen_packet_id(self):
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

    def get_device_id(self):
        # this is such a stupid hacky way to do this.
        return ''.join([chr(x) for x in self._connection.ctrl_transfer(0x80, 0x06, 0x0303, 0x0, 0x3c)[2::2]])

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
        try:
            self._receive()
        except usb.USBError:
            pass

    def init_fitbit(self):
        self.fitbit_control_init()
        self.init_device_channel([0xff, 0xff, 0x01, 0x01])

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

    def init_tracker_for_transfer(self):
        self._connection.reset()
        self.init_fitbit()
        self.wait_for_beacon()
        self.reset_tracker()

        # 0x78 0x02 is device id reset. This tells the device the new
        # channel id to hop to for dumpage
        cid = [random.randint(0,254), random.randint(0,254)]
        self.send_acknowledged_data([0x78, 0x02] + cid + [0x00, 0x00, 0x00, 0x00])
        self.close_channel()
        self.init_device_channel(cid + [0x01, 0x01])
        self.wait_for_beacon()
        self.ping_tracker()
        self.tracker = self.FitBitTracker()

    def reset_tracker(self):
        # 0x78 0x01 is apparently the device reset command
        self.send_acknowledged_data([0x78, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def wait_for_beacon(self):
        # FitBit device initialization
        while 1:
            try:
                d = self._receive()
                if d[2] == 0x4E:
                    break
            except usb.USBError:
                pass

    def _get_tracker_burst(self):
        d = self._check_burst_response()
        if d[1] != 0x81:
            raise Exception("Response received is not tracker burst! Got %s" % (d[0:2]))
        size = d[3] << 8 | d[2]
        if size == 0:
            return []
        return d[8:8+size]

    def run_opcode(self, opcode, payload = None):
        self.send_tracker_packet(opcode)
        data = self.receive_acknowledged_reply()
        if data[0] != self.tracker.current_packet_id:
            raise Exception("Tracker Packet IDs don't match! %02x %02x" % (data[0], self.tracker.current_packet_id))
        if data[1] == 0x42:
            return self.get_data_bank()
        if data[1] == 0x61:
            # Send payload data to device
            if payload is not None:
                self.send_tracker_payload(payload)
            data = self.receive_acknowledged_reply()
            if data[1] == 0x41:
                return [0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        if data[1] == 0x41:
            return [0x41, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]

    def send_tracker_payload(self, payload):
        # The first packet will be the packet id, the length of the
        # payload, and ends with the payload CRC
        p = [0x00, self.tracker.gen_packet_id(), 0x80, len(payload), 0x00, 0x00, 0x00, 0x00, reduce(operator.xor, map(ord, payload))]
        prefix = itertools.cycle([0x20, 0x40, 0x60])
        for i in range(0, len(payload), 8):
            current_prefix = prefix.next()
            plist = []
            if i+8 >= len(payload):
                plist += [(current_prefix + 0x80) | self._chan]
            else:
                plist += [current_prefix | self._chan]
            plist += map(ord, payload[i:i+8])
            while len(plist) < 9:
                plist += [0x0]
            p += plist
        # TODO: Sending burst data with a guessed sleep value, should
        # probably be based on channel timing
        self._send_burst_data(p, .01)

    def get_tracker_info(self):
        data = self.run_opcode([0x24, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        self.tracker.parse_info_packet(data)
        return data

    def send_tracker_packet(self, packet):
        p = [self.tracker.gen_packet_id()] + packet
        self.send_acknowledged_data(p)

    def ping_tracker(self):
        self.send_acknowledged_data([0x78, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    def check_tracker_data_bank(self, index):
        self.send_tracker_packet([0x60, 0x00, 0x02, index, 0x00, 0x00, 0x00])
        return self._get_tracker_burst()

    def run_data_bank_opcode(self, index):
        return self.run_opcode([0x22, index, 0x00, 0x00, 0x00, 0x00, 0x00])

    def get_data_bank(self):
        data = []
        while 1:
            try:
                bank = self.check_tracker_data_bank(self.tracker.current_bank_id)
                self.tracker.current_bank_id += 1
            except ANTReceiveException:
                continue
            if len(bank) == 0:
                return data
            data = data + bank

    def parse_bank2_data(self, data):
        for i in range(0, len(data), 13):
            print ["0x%.02x" % x for x in data[i:i+13]]
            # First 4 bytes are seconds from Jan 1, 1980
            print "Time: %s" % (datetime.datetime.fromtimestamp(data[i] | data[i + 1] << 8 | data[i + 2] << 16 | data[i + 3] << 24))

    def parse_bank0_data(self, data):
        print ["0x%.02x" % x for x in data]
        # First 4 bytes are a time
        i = 0
        while i < len(data):
            if not data[i] & 0x80:
                print "Time: %s" % (datetime.datetime.fromtimestamp(data[i+3] | data[i+2] << 8 | data[i+1] << 16 | data[i] << 24))
                i = i + 4
            else:
                print "%s" % [data[i], data[i+1], data[i+2]]
                i = i + 3
        
        
        # Read 3's until we get another time?
        # for i in range(0, len(data), 13):
        #     print ["0x%.02x" % x for x in data[i:i+13]]
        #     # First 4 bytes are seconds from Jan 1, 1980
        #     print "Time: %s" % (datetime.datetime.fromtimestamp(data[i] | data[i + 1] << 8 | data[i + 2] << 16 | data[i + 3] << 24))
        return
def main():
    device = FitBit(True)
    if not device.open():
        print "No devices connected!"
        return 1

    device.init_tracker_for_transfer()

    # device.get_tracker_info()
    # print device.tracker

    device.parse_bank2_data(device.run_data_bank_opcode(0x02))
    print "---"
    device.parse_bank0_data(device.run_data_bank_opcode(0x00))
    # device.run_data_bank_opcode(0x04)
    # d = device.run_data_bank_opcode(0x02) # 13
    # for i in range(0, len(d), 13):
    #     print ["%02x" % x for x in d[i:i+13]]
    # d = device.run_data_bank_opcode(0x00) # 7
    # print ["%02x" % x for x in d[0:7]]
    # print ["%02x" % x for x in d[7:14]]
    # j = 0
    # for i in range(14, len(d), 3):
    #     print d[i:i+3]
    #     j += 1
    # print "Records: %d" % (j)
    # d= device.run_data_bank_opcode(0x01) # 14
    # for i in range(0, len(d), 14):
    #     print ["%02x" % x for x in d[i:i+14]]
    device.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
