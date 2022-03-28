# BOSCH-MCMESS-Calibration-Protocol-for-RPi
Implement Bosch MCMESS protocol, It is a calibration protocol for the K-line on Raspberry Pi

====================================
The Bosch McMESS-Protocol in the ME7
====================================

The McMESS protocol is a proprietary protocol of Bosch. It is a calibration protocol 
for the K-line (should be same use case as the CAN calibration protocol CCP).
McMESS is used in the process of tuning and optimizing the ECU for a certain combination of 
engine and vehicle model.  Normally a special application system of the vehicle manufacturer
will communicate with the ECU using McMESS over the K-line.

The name of the protocol would mean something like "microcontroller measurement protocol",
so "mess" stands for measurement (in german: "Messung").  But I think the english term "mess"
is quite good - it's just a mess. McMESS is a braindead, obfuscating protocol implementation. 
It uses: 9bit transfer - hard to achieve on a PC, but possible when abusing the parity bit,
10400baud and 125000baud communication speed - the latter not possible with a standard PC serial port
(could be possible with USB-Serial converters or special serial itf cards or when using a microcontroller).

Mainly, the protocol provides the possibility to read and write values in the RAM, also while the engine 
is running (change parameters in the ECU, log variables), but the reachable speed is not very high
(270..1000bytes/second). So most of this is not very interesting for normal tuning/logging purposes.

One useful thing is the possibility to read out the EPK string using this protocol.
For example, the EPK-String of a 1.8T CH-box is: "40/1/ME7.5/5/4012.01//24b/Dst01o/110700//"
The first number is the string length, "Dst01o" is for "Datenstand 01o"/data version 01o, 
and the last number is for the date 11-JUL-2000.  
A small application program could retrieve this information out of the ECU using McMESS.
The EPK string is also referenced in damos files, so this allows to match an ECU to a damos file.


Variables used:
===============
The damos/a2l variables/constants which are related to this protocol are the following:
B_mcacti    -> Flag showing that the McMESS is active
CWVSV       -> CW to disable writing to "Verstellsystem" variables (0 = disabled)
               ("Verstellsystem" means: variable change system)
SY_TURBO    -> system constant turboloader present
SY_NWS      -> system constant variable camshaft (0=none, 1=2-point, 2=continuous)

Variables of the Verstellsystem, that can be changed are:
vsdmr
vsfpses  
vsfrk 
vske 
vsldtv 
vsns
vsrlmx 
vsvw 
vswnws 
vszw 
vszwkr[0..7]
vswnws


Starting a sesssion
===================
There are two ways to start a McMESS session:
1. with a normal fastinit pulse and an "A0" request messsage:
   a) fast init pulse 25ms low / 25ms high, send 82 10 F1 A0 A5 <cks> (10400baud,8N1) 
        -> receive 03 E0 A5 0D cks (10400baud,8N1) => connected with normal speed (10400bd)
   b) fast init pulse 25ms low / 25ms high, send 82 10 F1 A0 A6 <cks> (10400baud,8N1) 
        -> receive 03 E0 A6 0D cks (10400baud,8N1) => connected with highspeed (125000bd)

2. with a special init pulse of 80ms:
   a) fast init 80ms low pulse, send A5 (10400baud,9N2) 
        -> receive 10D (10400baud,9N2)   => connected with normal speed (10400bd)
   b) fast init 80ms low pulse, send A6 (10400baud,9N2) 
        -> receive 10D (10400baud,9N2)   => connected with highspeed (125000bd)

After being connected, switch to:
- 9bits, no parity, 1stop bit, 10400baud for normal speed
or
- 9bits, no parity, 2stop bits, 125000baud for highspeed

The communication timeout is 2 seconds. 
After this time, without sending data, the communication session will be terminated by the ECU.


Communication
=============
Every 20ms a new message can be processed (the internal task timing in the ECU is defining this)
-> very slow, there is no real need for highspeed communication mode (125000baud) for the simple commands.
Highspeed mode is only a prerequisite for reading variables synchronously to crankshaft (see below commands).

There are some protocol variables which can be set by the tester and which are used during the communication.
All variables have one byte size:

newData         set to <low-addr> if the tester sends two address bytes (<high-addr>, <low-addr>)
                initialized to zero on connection setup

lowAddress      set by command 0x125 (setLowAddress) from newData
                (it is used also as table index)

highAddress     set by command 0x126 (setHighAddress) from newData

dataByte        set by command 0x134 (setDataByte) from newData



Two different things can be done by the application system (tester) after
a communication session was started:
1. Direct-address-read
2. COMMANDS

1. Direct-address-read:
-----------------------
The application system (tester) sends two address bytes with bit9 = 0. These two bytes are interpreted
as high and low of an address in IRAM, XRAM, or EXTRAM.  The ECU then responds with two bytes read 
from the address in RAM or 0x0000 if the address is outside RAM memory:

Application system      ECU
<high-address> 
<low-address>
                        <memory-contents-of-address>
                        <memory-contents-of-address+1>

A maximum speed of about 270 Bytes/sec is reached when using normal speed (10400 baud) connection.
A maximum speed of about 1000 Bytes/sec is reached when using highspeed (125000baud) connection.
The address is mapped as follows:
0x0000 .. 0x3FFF    => 0x380000 .. 0x383FFF (EXTRAM)
0xC000 .. 0xFFFF    => 0x00C000 .. 0x00FFFF (XRAM, IRAM)
For other addresses the ECU will just return a value of 0x0000.

ATTENTION: as a side effect of this, the <low-address> sent by the tester is also stored in the variable "newData".
This variable is used within some commands (see below). Sending two address bytes is the only way to set "newData"
to a certain value!


2. COMMANDS:
------------
The tester sends just one 9bit command value and the ECU responds with one 9bit response value:

Application system      ECU
<command> 
                        <response>

All commands have set bit9 to 1!  
Possible error responses to commands (all errors have bit9 = 0):
    0x0EB - unknown command
    0x0ED - the command needs the highspeed mode
    0x0E2 - no data byte was set before
    0x0E1 - incorrect address or index for this command


The possible commands are:
--------------------------
//------------------------------------------------------------------------------------------------------------
// Disabled commands (might be useable in some ECU images)
0x113  not implemented -> returns 0x0EB
0x115  not implemented -> returns 0x0EB
0x116  not implemented -> returns 0x0EB
0x10B  (readFromFlashMemory_DISABLED):
    -> (function would be: read memory out of flash, increment lowAddress), 
    -> returns always 0x0E1


//------------------------------------------------------------------------------------------------------------
// Reading/writing of protocol variables:
0x102 (readNewData):
    -> returns 0x100|newData  (the variable newData can be set ONLY from <low-addr> in a direct-address-read)

0x104 (readLowAddress):
    -> returns 0x100|lowAddress

0x107 (readHighAddress):
    -> returns 0x100|highAddress


0x125 (setLowAddress):
    -> set lowAddress (index) = newData
    -> returns 0x100|(lowAddress ^ 25)

0x126 (setHighAddress):
    -> set highAddress = newData
    -> returns 0x100|(highAddress ^ 26)

0x134 (setDataByte):
    -> set dataByte = newData
    -> sets status bit DATABYTE_SET
    -> returns 0x100|(dataByte ^ 34)


//------------------------------------------------------------------------------------------------------------
// Reading of EPK string (to check version of the running image):
0x119 (getStringEPK):
    if lowAddress == 0: 
        -> get length of EPK string, increment lowAddress, 
        -> returns 0x0EE in error case (stringlength_EPK > 80 || num_digits_strlen_epk < 1 or > 3)
        -> returns 0x100|stringlength_EPK
    if lowAddress > 0:
        -> return 0x0EE if lowAddress + num_digits_strlen_epk > 80
        -> returns 0x100|stringEPK[num_digits_strlen_epk + lowAddress]
        -> increment lowAddress


//------------------------------------------------------------------------------------------------------------
// Direct reading/writing of memory:
0x10E (readFromRAMMemory):
    -> returns 0x0E1, if the address (highAddress,lowAddress) is not OK (not in IRAM, XRAM, EXTRAM)
    -> returns 0x100|memory[mapped_address(highAddress,lowAddress)] , increment lowAddress

0x12F (writeToRAMMemory):
    -> returns 0x0E2, if status bit DATABYTE_SET is not set
    -> returns 0x0E1, if address (highAddress,lowAddress) is not OK (not IRAM, XRAM, or EXTRAM)
    -> returns 0x100|(dataByte ^ 2F), writes memory[mapped_address(highAddress,lowAddress)] = dataByte
    -> increment lowAddress

  mapped_address:
    0x0000 .. 0x3FFF -> EXTRAM
    0xC000 .. 0xFFFF -> IRAM, XRAM


//------------------------------------------------------------------------------------------------------------
// "Verstellsystem": this allows to read and/or change 17 predefined variables of the application tuning system
// [0]  vszw        (default = 00)      Zuendwinkel
// [1]  vsfrk       (default = 80)      Gemischfaktor
// [2]  vsvw        (default = 00)      Vorlagerungswinkel
// [3]  vsns        (default = 00)      Solldrehzahl
// [4]  vszwkr[0]   (default = 00)      Zuendwinkel Zdg. 1
// [5]  vszwkr[1]   (default = 00)      Zuendwinkel Zdg. 2
// [6]  vszwkr[2]   (default = 00)      Zuendwinkel Zdg. 3
// [7]  vszwkr[3]   (default = 00)      Zuendwinkel Zdg. 4
// [8]  vszwkr[4]   (default = 00)      Zuendwinkel Zdg. 5
// [9]  vszwkr[5]   (default = 00)      Zuendwinkel Zdg. 6
// [10] vszwkr[6]   (default = 00)      Zuendwinkel Zdg. 7
// [11] vszwkr[7]   (default = 00)      Zuendwinkel Zdg. 8
// [12] vske        (default = 00)      Klopferkennungsschwelle
// [13] vsdmr       (default = 00)      Drehmomentreserve
// [14] vsfpses     (default = 80)      Saugrohrdruck
// [15] vsrlmx      (default = 00)      Max. rl fuer LDR
// [16] vsldtv      (default = 00)      TV LDR bei App-Steuerung
//Optional, if variable camshaft is present:
// [17] vswnws                          Winkel NW fuer VANOS



0x138 (initializeVerstellsystemVariables):
    -> returns 0x138, initializes all 17 variables to default values
        (this initialization is done also on connection setup)

0x11F (readNextVerstellsystemVariable):
    -> returns 0x0E1, if lowAddress > 17
    -> returns 0x100|vs_variable[lowAddress]]
    -> increment lowAddress

0x137 (writeNextVerstellsystemVariable):
    -> returns 0x0E2, if bit DATABYTE_SET is not set or [CWVSV] == 0
    -> returns 0x0E1, if index is > 17
    -> vs_variable[lowAddress] = newData
    -> returns 0x100|(index ^ 37)
    -> increment lowAddress


//------------------------------------------------------------------------------------------------------------
// "SyncAddress": this allows to define 6 byte locations in RAM which can be read synchronously to the crankshaft.
//      -> possible to read out values for up to 6 cylinders each crankshaft revolution.
//      -> works only in highspeed (125000bd) connection mode
0x110 (highspeed_readFromSyncAddressTable):
    -> returns 0x0ED, if not highspeed connection (125000bd)
    -> returns 0x0E1, if lowAddress is >= 12
    -> returns 0x100|sync_address_table[lowAddress], increment lowAddress
           delivers high or low byte, depending on odd/even lowAddress.

0x131 (highspeed_writeToSyncAddressTable):
    -> returns 0x0ED, if not highspeed connection (125000bd)
    -> returns 0x0E1, if lowAddress is >= 12
    -> returns 0x0E1, if the sync_address is not OK, the address check is performed after writing the highByte
    -> sync_address_table[lowAddress] = newData, increment lowAddress, 
       uses newData as lowByte (lowAddress even) or highByte (lowAddress odd) of the sync_address
    -> returns 0x100|(newData ^ 31)

0x13D (highspeed_gotoReadSyncValues):
    -> returns 0x0ED, if not highspeed connection (125000bd)
    -> switch communication mode to SYNC-VALUE-READING-MODE
    -> returns 0x13D


SYNC-VALUE-READING-MODE:
ATTENTION: this mode is served only when getting signals from G28 (crankshaft rotating),
if the engine is not running, communication timeout will happen after 500ms.
In this communication mode, ECU responses are not triggered on a regular interval of 20ms as in normal mode,
but the ECU response is triggered synchronously to the crankshaft(?) by an interrupt.
Triggered by XP1INT, derived from CC15INT, derived from sensor G28 (?).
The timing (how fast the ECU sends a response) depends on the engine speed.

=> used to report 6 (userdefined) measurement variables from RAM:
    Tester sends 0x1XX  -> ECU returns 6 bytes (variables read from the locations in sync_address_table)
    Tester sends 0x1AA  -> ECU returns 0x155, goes back to normal communication mode



EXAMPLES
--------
TESTER:
        ECU:

#Set newData to 0x00
0x040
0x000
        0x000
        0x000

# Set dataByte to 0x00
0x040
0x000
        0x000
        0x000
0x134
        0x134
