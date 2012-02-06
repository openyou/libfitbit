#!/usr/bin/env python
#################################################################
# ant message protocol
# By Kyle Machulis <kyle@nonpolynomial.com>
# http://www.nonpolynomial.com
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
# Added to and untwistedized and fixed up by Kyle Machulis <kyle@nonpolynomial.com>
#

import operator, struct, array, time

class ANTReceiveException(Exception):
    pass

def hexList(data):
    return map(lambda s: chr(s).encode('HEX'), data)

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
        self._receiveBuffer = []

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

    def _check_reset_response(self, status):
        for tries in range(8):
            try:
                data = self._receive_message()
            except ANTReceiveException:
                continue
            if len(data) > 3 and data[2] == 0x6f and data[3] == status:
                return
        raise ANTStatusException("Failed to detect reset response")

    def _check_ok_response(self):
        # response packets will always be 7 bytes
        status = self._receive_message()

        if len(status) == 0:
            raise ANTStatusException("No message response received!")

        if status[2] == 0x40 and status[5] == 0x0:
            return

        raise ANTStatusException("Message status %d does not match 0x0 (NO_ERROR)" % (status[5]))

    def reset(self):
        if self._debug:
            print "ANT.reset() requested"
        self._send_message(0x4a, 0x00)
        # According to protocol docs, the system will take a maximum
        # of .5 seconds to restart
        #
        # sleep time was 0.6, changed to 1.0 which reduces fail rate; a retry might
        # be more sensible but wasn't sure if that might lead to possible duplicate 
        # acknowledgements in the receive queue. A setting of 2.0 caused the interface 
        # to not read fitbit devices. - Reed 31 Dec 2011
        #
        time.sleep(1.0)
        #
        # This is a requested reset, so we expect back 0x20
        # (COMMAND_RESET)
        self._check_reset_response(0x20)
        if self._debug:
            print "ANT.reset() done"

    def set_channel_frequency(self, freq):
        if self._debug:
            print "ANT.set_channel_frequency()",freq
        self._send_message(0x45, self._chan, freq)
        self._check_ok_response()

    def set_transmit_power(self, power):
        if self._debug:
            print "ANT.set_transmit_power()", power
        self._send_message(0x47, 0x0, power)
        self._check_ok_response()

    def set_search_timeout(self, timeout):
        if self._debug:
            print "ANT.set_search_timeout()", self._chan, timeout
        self._send_message(0x44, self._chan, timeout)
        self._check_ok_response()

    def send_network_key(self, network, key):
        if self._debug:
            print "ANT.send_network_key()", network, key
        self._send_message(0x46, network, key)
        self._check_ok_response()

    def set_channel_period(self, period):
        if self._debug:
            print "ANT.set_channel_period()", self._chan, period
        self._send_message(0x43, self._chan, period)
        self._check_ok_response()

    def set_channel_id(self, id):
        if self._debug:
            print "ANT.set_channel_id()", self._chan, id
        self._send_message(0x51, self._chan, id)
        self._check_ok_response()

    def open_channel(self):
        if self._debug:
            print "ANT.open_channel()", self._chan
        self._send_message(0x4b, self._chan)
        self._check_ok_response()

    def close_channel(self):
        if self._debug:
            print "ANT.close_channel()", self._chan
        self._send_message(0x4c, self._chan)
        self._check_ok_response()

    def assign_channel(self):
        if self._debug:
            print "ANT.assign_channel()", self._chan
        self._send_message(0x42, self._chan, 0x00, 0x00)
        self._check_ok_response()

    def receive_acknowledged_reply(self, size = 13):
        if self._debug:
            print "Start receive_acknowledged_reply"
        for tries in range(30):
            status = self._receive_message(size)
            if len(status) > 4 and status[2] == 0x4F:
                if self._debug:
                    print "End receive_acknowledged_reply"
                return status[4:-1]
        if self._debug:
            print "Fail receive_acknowledged_reply"
        raise ANTReceiveException("Failed to receive acknowledged reply")

    def _check_tx_response(self, maxtries = 16):
        if self._debug:
            print "Start _check_tx_response"
        for msgs in range(maxtries):
            status = self._receive_message()
            if len(status) > 5 and status[2] == 0x40:
                if status[5] == 0x0a: # TX Start
                    continue
                if status[5] == 0x05: # TX successful
                    if self._debug:
                        print "End _check_tx_response"
                    return;
                if status[5] == 0x06: # TX failed
                    if self._debug:
                        print "Fail _check_tx_response"
                    raise ANTReceiveException("Transmission Failed")
        if self._debug:
            print "FailFinal _check_tx_response"
        raise ANTReceiveException("No Transmission Ack Seen")

    def _send_burst_data(self, data, sleep = None):
        if self._debug:
            print "Start _send_burst_data(%s)" % (data)
        for tries in range(2):
            for l in range(0, len(data), 9):            
                self._send_message(0x50, data[l:l+9])
                # TODO: Should probably base this on channel timing
                if sleep != None:
                    time.sleep(sleep)
            try:
                self._check_tx_response()
            except ANTReceiveException:
                continue
            if self._debug:
                print "End _send_burst_data"
            return
        if self._debug:
            print "Fail _send_burst_data"
        raise ANTReceiveException("Failed to send burst data")

    def _check_burst_response(self):
        if self._debug:
            print "Start _check_burst_response"
        response = []
        for tries in range(16):
            status = self._receive_message()
            if len(status) > 5 and status[2] == 0x40 and status[5] == 0x4:
                raise ANTReceiveException("Burst receive failed by event!")
            elif len(status) > 4 and status[2] == 0x4f:
                response = response + status[4:-1]
                if self._debug:
                    print "End _check_burst_response"
                return response
            elif len(status) > 4 and status[2] == 0x50:
                response = response + status[4:-1]
                if status[3] & 0x80:
                    if self._debug:
                        print "End _check_burst_response"
                    return response
        if self._debug:
            print "Fail _check_burst_response"
        raise ANTReceiveException("Burst receive failed to detect end")

    def send_acknowledged_data(self, l):
        if self._debug:
            print "Start _send_acknowledged_data(%s)" % (l)
        for tries in range(8):
            try:
                self._send_message(0x4f, self._chan, l)
                self._check_tx_response()
            except ANTReceiveException:
                continue
            if self._debug:
                print "End _send_acknowledged_data"
            return
        if self._debug:
            print "Fail _send_acknowledged_data"
        raise ANTReceiveException("Failed to send Acknowledged Data")

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
        data.append(reduce(operator.xor, data))

        if self._debug:
            print "    sent: " + hexRepr(data)
        return self._send(map(chr, array.array('B', data)))

    def _find_sync(self, buf, start=0):
        i = 0;
        for v in buf:
            if i >= start and (v == 0xa4 or v == 0xa5):
                break
            i = i + 1
        if i != 0:
            if self._debug:
                print "Searching for SYNC, discarding: " + hexRepr(buf[0:i])
            del buf[0:i]
        return buf

    def _receive_message(self, size = 4096):
        timeouts = 0
        data = self._receiveBuffer
        l = 4 # Minimum packet size (SYNC, LEN, CMD, CKSM)
        while True:
            if len(data) < l:
                # data[] too small, try to read some more
                from usb.core import USBError
                try:
                    data += self._receive(size).tolist()
                    timeouts = 0
                except USBError:
                    timeouts = timeouts+1
                    if timeouts > 3:
                        # It looks like there isn't anything else coming.  Try
                        # to find a plausable packet..
                        data = self._find_sync(data)
                        while len(data) > 1 and len(data) < data[1]+4:
                            data = self._find_sync(data, 2)
                        if len(data) == 0:
                            # Failed to find anything..
                            self._receiveBuffer = []
                            return []
                continue
            data = self._find_sync(data)
            if len(data) < l: continue
            if data[1] < 0 or data[1] > 32:
                # Length doesn't look "reasonable"
                data = self._find_sync(data, 1)
                continue
            l = data[1] + 4
            if len(data) < l:
                continue
            p = data[0:l]
            if reduce(operator.xor, p) != 0:
                if self._debug:
                    print "Checksum error for proposed packet: " + hexRepr(p)
                data = self._find_sync(data, 1)
                continue
            self._receiveBuffer = data[l:]
            if self._debug:
                print "received: " + hexRepr(p)
            return p

    def _receive(self, size=4096):
        raise Exception("Need to define _receive function for ANT child class!")

    def _send(self):
        raise Exception("Need to define _send function for ANT child class!")

