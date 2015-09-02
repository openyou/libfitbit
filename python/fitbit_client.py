#!/usr/bin/env python
#################################################################
# python fitbit web client for uploading data to fitbit site
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

import sys
import urllib
import urllib2
import urlparse
import base64
import xml.etree.ElementTree as et
from fitbit import FitBit
from antprotocol.bases import FitBitANT, DynastreamANT

class FitBitResponse(object):
    def __init__(self, response):
        self.current_opcode = {}
        self.opcodes = []
        self.root = et.fromstring(response.strip())
        self.host = None
        self.path = None
        self.response = None
        if self.root.find("response") is not None:
            self.host = self.root.find("response").attrib["host"]
            self.path = self.root.find("response").attrib["path"]
            if self.root.find("response").text:
                # Quick and dirty url encode split
                response = self.root.find("response").text
                self.response = dict(urlparse.parse_qsl(response))

        for opcode in self.root.findall("device/remoteOps/remoteOp"):
            op = {}
            op["opcode"] = [ord(x) for x in base64.b64decode(opcode.find("opCode").text)]
            op["payload"] = None
            if opcode.find("payloadData").text is not None:
                op["payload"] = [x for x in base64.b64decode(opcode.find("payloadData").text)]
            self.opcodes.append(op)
    
    def __repr__(self):
        return "<FitBitResponse object at 0x%x opcode=%s, response=%s>" % (id(self), str(self.opcodes), str(self.response))

class FitBitClient(object):
    CLIENT_UUID = "2ea32002-a079-48f4-8020-0badd22939e3"
    #FITBIT_HOST = "http://client.fitbit.com:80"
    FITBIT_HOST = "https://client.fitbit.com" # only used for initial request
    START_PATH = "/device/tracker/uploadData"
    DEBUG = True
    BASES = [FitBitANT, DynastreamANT]

    def __init__(self):
        self.info_dict = {}
        self.fitbit = None
        for base in [bc(debug=self.DEBUG) for bc in self.BASES]:
            for retries in (2,1,0):
                try:
                    if base.open():
                        print "Found %s base" % (base.NAME,)
                        self.fitbit = FitBit(base)
                        self.remote_info = None
                        break
                    else:
                        break
                except Exception, e:
                    print e
                    if retries:
                        print "retrying"
                        time.sleep(5)
            else:
                raise
            if self.fitbit:
                break
        if not self.fitbit:
            print "No devices connected!"
            exit(1)

    def form_base_info(self):
        self.info_dict.clear()
        self.info_dict["beaconType"] = "standard"
        self.info_dict["clientMode"] = "standard"
        self.info_dict["clientVersion"] = "1.0"
        self.info_dict["os"] = "libfitbit"
        self.info_dict["clientId"] = self.CLIENT_UUID
        if self.remote_info:
            self.info_dict = dict(self.info_dict, **self.remote_info)

    def run_upload_request(self):
        try:
            self.fitbit.init_tracker_for_transfer()

            url = self.FITBIT_HOST + self.START_PATH

            # Start the request Chain
            self.form_base_info()
            while url is not None:
                req = urllib2.Request(url, urllib.urlencode(self.info_dict))
                req.add_header("User-Agent", "FitBit Client")
                res = urllib2.urlopen(req).read()
                print res
                r = FitBitResponse(res)
                self.remote_info = r.response
                self.form_base_info()
                op_index = 0
                for o in r.opcodes:
                    self.info_dict["opResponse[%d]" % op_index] = base64.b64encode(''.join([chr(x) for x in self.fitbit.run_opcode(o["opcode"], o["payload"])]))
                    self.info_dict["opStatus[%d]" % op_index] = "success"
                    op_index += 1
                urllib.urlencode(self.info_dict)
                print self.info_dict
                if r.host:
                    url = "http://%s%s" % (r.host, r.path)
                    print url
                else:
                    print "No URL returned. Quitting."
                    break
        except:
            self.fitbit.base.close()
            raise
        self.fitbit.command_sleep()
        self.fitbit.base.close()

def main():
    f = FitBitClient()
    f.run_upload_request()    
    return 0

if __name__ == '__main__':
    import time
    import traceback
    
    cycle_minutes = 15
    
    while True:
        try:
            main()
        except Exception, e:
            print "Failed with", e
            print
            print '-'*60
            traceback.print_exc(file=sys.stdout)
            print '-'*60
        else:
            print "normal finish"
            print "restarting..."
    
    #sys.exit(main())

