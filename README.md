libfitbit
=========

by Kyle Machulis <kyle@nonpolynomial.com>

Nonpolynomial Labs - [http://www.nonpolynomial.com](http://www.nonpolynomial.com)

libfitbit is part of the OpenYou project for Open Source Health
Hardware access - [http://openyou.org](http://openyou.org)

If you find libfitbit useful, please donate to the project at
[http://pledgie.com/campaigns/14375](http://pledgie.com/campaigns/14375)

**WARNING:** This project is **only** for the ANT based **Fitbit Ultra**
tracker. Newer trackers like the One, the Zip, the Flex, the Force and
maybe upcoming ones use the bluetooth protocol, and are thus incompatible
with this project. If you are looking for a utility to synchronise your
bluetooth based tracker with the Fitbit services, have a look at
[https://bitbucket.org/benallard/galileo](https://bitbucket.org/benallard/galileo) .

Credits and Thanks
------------------

Thanks to Matt Cutts for hooking me up with the hardware -
http://www.twitter.com/mattcutts


Description
-----------

libfitbit is an implementation of the data retrieval protocol for the
fitbit health tracking device. It also implements a synchronization
client for synchronizing data with the fitbit website on platforms not
supported by Fitbit currently.

The main goal of the library is to augment the services already
provided by the fitbit website, allowing for developers to make
interesting new applications that access the fitbit data in smaller
time chunks on the local machine, as well as giving users the ability
to back up their own data without having to rely on the web service.

Currently, the library only implements a proof of concept of the
protocol and web interface in python. This will be turned into a C
library, which can then be SWIG'd or otherwise interfaced to other
languages.

The fitbit reverse engineering document in the doc directory may also
be used for implementing the protocol in new languages without having
to read code (not that my ability to convey the protocol in english is
all that clear).


Package Information
-------------------

Source repo @ [http://www.github.com/qdot/libfitbit](http://www.github.com/qdot/libfitbit)


Platform Support
----------------

* Linux - Tested on Ubuntu 10.10
* OS X - Untested, should work?
* Windows - Won't work at the moment. May be able to create serial
  interface to talk to CP2012 chip? Haven't done research yet.


Library Requirements
--------------------

* Python - http://www.python.org
* libusb-1.0 - http://www.libusb.org
* pyusb 1.0+ - http://sourceforge.net/projects/pyusb/files/


Platform Cavaets
----------------

### Linux

You'll need to either run as root or set up a udev rule to switch out
permissions on the base VID/PID. We'll hopefully have a udev rule
checked in shortly.

### OS X

FitBit original driver is claiming the device resulting in premission errors
when libusb wants to claims it.

A solution that works everytime is simply to disable the driver by renaming
it:

```bash
cd /System/Library/Extensions
sudo mv SiLabsUSBDriver.kext SiLabsUSBDriver.kext.disabled
```

And reboot.

To re-enable it, just rename it again, and reboot again.

### Windows

Don't even know if it works there yet. :D


Future Plans
------------

* Breaking ANT access library out into its own repo
* Windows support
* Finish figuring out data types
* Implement library in C


License
-------

```
Copyright (c) 2011, Kyle Machulis/Nonpolynomial Labs
All rights reserved.

Redistribution and use in source and binary forms, 
with or without modification, are permitted provided 
that the following conditions are met:

   * Redistributions of source code must retain the 
     above copyright notice, this list of conditions 
     and the following disclaimer.
   * Redistributions in binary form must reproduce the 
     above copyright notice, this list of conditions and 
     the following disclaimer in the documentation and/or 
     other materials provided with the distribution.
   * Neither the name of the Nonpolynomial Labs nor the names 
     of its contributors may be used to endorse or promote 
     products derived from this software without specific 
     prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND 
CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, 
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT 
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; 
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN 
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, 
EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
