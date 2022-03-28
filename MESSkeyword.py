#!/usr/bin/python3
import os
import sys
import serial
import array
import termios
import fcntl
import time
import subprocess
from ctypes import *


# -------------------------------------------------------------
# ---------------- KLINE Bus Send Diag frame ------------------
# -------------------------------------------------------------
# -------------------------------------------
# FMT | Tgt | Src | Data[n]....Data[0] | CS
# -------------------------------------------
WAKEUP_DEFAULT_PERIODE = 25
KLN_WAKEUP_DATA = 0xF0
KLN_START_COM = 0x81
MCMESS_FAST_INIT1 = 0xA0
MCMESS_FAST_INIT2 = 0xA2

class Ser4McMessInterface(object):
    def __init__(self, CGTid = 0):
        # -- open Serial Port --
        #parity   - PARITY_NONE  #PARITY_MARK:Parity=1 #PARITY_SPACE:Parity=0
        #stopbits – STOPBITS_ONE #STOPBITS_ONE_POINT_FIVE #STOPBITS_TWO
        self.SerPort = serial.Serial('/dev/ttyAMA0', timeout = 0.3, parity = serial.PARITY_NONE,stopbits=serial.STOPBITS_ONE)
        self.SerPort.flushOutput()
        self.SerPort.flushInput()
        self._Baudrate(200)
            
    ### McMess Command Request ###
    def _MessCmdSend(self, Cmd):
        self.SerPort.baudrate =125000 
        ### Baudrate: 125K and data size 9bit 2 stopbit###
        self.SerPort.stopbits = serial.STOPBITS_TWO
        ### for Commands ###
        self.SerPort.parity = serial.PARITY_MARK#PARITY_SPACE#PARITY_MARK

        self.SerPort.write(serial.to_bytes([Cmd]))

        flag, resp = self._LoopBackRecv([Cmd])

        if flag == 0:
            return 0, 0
        else:
            flag, resp
            
    ### McMess DirectAddressRead Request ###
    def _MessDarSend(self, AddrHi, AddrLo):
        self.SerPort.baudrate =125000 
        ### Baudrate: 125K and data size 9bit 2 stopbit###
        self.SerPort.stopbits = serial.STOPBITS_TWO
        ### for Direct Read ###
        self.SerPort.parity = serial.PARITY_SPACE#PARITY_SPACE#PARITY_MARK
        
        self.SerPort.write(serial.to_bytes([AddrHi, AddrLo]))

        flag, resp = self._LoopBackRecv([AddrHi, AddrLo])
        if flag == 0:
            return 0, 0
        else:
            flag, resp

    def _MessDarRecv(self):
        try:
            DataHi = int(ord(self.SerPort.read()))
            DataLo = int(ord(self.SerPort.read()))
            return 0, [DataHi,DataLo]
        except:
            return -1,[0,0]

    def _MessCmdRecv(self):
        try:
            Resp = int(ord(self.SerPort.read()))
            return 0, Resp
        except:
            return -1,0
            
    def Connect(self):
        self._Wakeup()
        McMessReq=[0x81, 0x11, 0xF1, 0x81, 0x4]
        self.SerPort.write(serial.to_bytes(McMessReq))
        ### Read the LoopBack Data ###
        self._LoopBackRecv(McMessReq)
        ### Read the response ###
        flag, error = self._Recv()
        #print('McMessKlineStart',flag, error)
        
        if self.Mode:### High Speed 125K ###
            ### Baudrate: 10400 and data size 9bit 1 stopbit ###
            ### McMess Fast Init Request ###
            McMessReq=[0x82, 0x11, 0xF1, 0xA0, 0xA6, 0xCA]
            self.SerPort.write(serial.to_bytes(McMessReq))
            ### Read the LoopBack Data ###
            self._LoopBackRecv(McMessReq)
            ### Read the response ###
            flag, error = self._Recv()
            
            self._Baudrate(125000) 
            ### Baudrate: 125K and data size 9bit 2 stopbit###
            self.SerPort.stopbits = serial.STOPBITS_TWO

        else:### Low Speed 10400 ###
            ### Baudrate: 10400 and data size 9bit 1 stopbit ###
            ### McMess Fast Init Request ###
            McMessReq=[0x82, 0x11, 0xF1, 0xA0, 0xA5, 0xC9]
            self.SerPort.write(serial.to_bytes(McMessReq))
            ### Read the LoopBack Data ###
            self._LoopBackRecv(McMessReq)
            ### Read the response ###
            flag, error = self._Recv()

        return 0,[0,0]
        
    def CmdReadVersion(self):
        RetData=[]
        McMessReq=0x19

        self._MessCmdSend(McMessReq)

        ### Read the response ###
        stat, resp = self._MessCmdRecv()
        #print('CmdReadVersion',stat, resp )
        Ttotal=time.time()
        for idx in range(resp):
            self._MessCmdSend(McMessReq)
            ### Read the response ###
            stat, resp = self._MessCmdRecv()
            
            if stat==0:
                RetData.append(resp&0xFF)
            else:
                RetData=[0]
                break
        #print('\nTotalReadTime: %s'%(time.time()-Ttotal))
        #print('Resp: %s'%(''.join(chr(data) for data in RetData)))
        return 0,RetData
        
    def DirectRead(self,Address):
        ### McMess Fast Init Request ###
        AddrLo= Address&0xFF
        AddrHi= (Address>>8)&0xFF

        self._MessDarSend(AddrHi,AddrLo)
        ### Read the response ###
        stat, resp = self._MessDarRecv()

        #print('DirectRead:',resp )

        return stat,resp

    
    def GetVar(self, VarType, VarAddr):
        ### Send variable address and size to ECU and get value ####
        if VarType == 'UBYTE' or VarType == 'SBYTE' or VarType == 'UWORD' or VarType == 'SWORD':
            stat,Response = self.DirectRead(VarAddr)
            
            if stat == -1:
                return -1,-1
        elif VarType == 'ULONG' or VarType == 'SLONG':
            stat,Response = self.DirectRead(VarAddr)
            if stat == -1:
                return -1,-1
            stat,ResponseL = self.DirectRead(VarAddr+2)
            if stat == -1:
                return -1,-1
            Response.append(ResponseL[0])
            Response.append(ResponseL[1])
      
        return (0, Response)


    def Close(self):
        self.SerPort.close()
        return 0, 0
            
    def _Wakeup(self):
        WakeupDeviate = 0
        # -- Set Baud rate on 200 --
        self._Baudrate(200)
        # --------------------------
        self.SerPort.write(serial.to_bytes([KLN_WAKEUP_DATA]))
        # ReInitialize Baudrate --
        self._Baudrate(10400)
            
    def _Send(self, data):
        # -- Calculate Checksum --
        Checksum = self._CheckSum(data)
        data.append(Checksum)
        
        # -- Send Data --
        if len(data)<20:
            pass
        for byte in data:
            self.SerPort.write(serial.to_bytes([byte]))

        flag, error = self._LoopBackRecv(data)
        if flag == 0:
            return 0, 0
        else:
            flag, error
            
    
    def _Recv(self):
        self.AddLen = 0
        self.RxData = []
        try:
            Data = int(ord(self.SerPort.read()))
        except Exception as error:
            return -1, [error]
        self.RxData.append(Data)

        if Data != b'':
            RxFormat = Data & 0xC0
            DataLen = Data & 0x3F
            if DataLen != 0:
                if RxFormat == 0:
                    DataLen += 1                                # -- Checksum --
                else:
                    DataLen += 3                                # -- TargetAddr+SourceAddr+Checksum --
            else:                                               # -- Additional length --
                self.AddLen = 1
                TargetID = int(ord(self.SerPort.read()))
                SourceID = int(ord(self.SerPort.read()))
                DataLen  = int(ord(self.SerPort.read()))           # -- Data, CheckSum --

                self.RxData.append(TargetID)
                self.RxData.append(SourceID)
                self.RxData.append(DataLen)
                DataLen+=1
                
            for i in range(DataLen):
                Data = int(ord(self.SerPort.read()))
                self.RxData.append(Data)
        return 0, self.RxData
    
    def _Baudrate(self, baudrate):
        if baudrate == 10400 or baudrate == 200 or baudrate == 125000:
            # -- Set Baud rate on 10400 --
            buf=array.array('i', [0] * 64)   
            fcntl.ioctl(self.SerPort, 0x802C542A, buf)
            buf[2] &= ~termios.CBAUD
            buf[2] |= 0o010000
            buf[9] = buf[10] = baudrate
            fcntl.ioctl(self.SerPort, 0x402C542B, buf)
        else:
            self.SerPort.baudrate = baudrate
        self.Buadrate = baudrate
        
    def _CheckSum(self, data):
        Checksum = 0
        for byte in data:
            Checksum += byte
        Checksum &= 0x00FF

        return Checksum
    
    def _LoopBackRecv(self, data):
        # -- Read Loop Back Data from Transciver --
        LoopBackData = []
        for index in range(len(data)):
            try:
                LBdata = int(ord(self.SerPort.read()))
            except:
                return -1, '!!!Port Error'
            if LBdata != b'':
                LoopBackData.append(LBdata)
                if LoopBackData[0] == 0xF0 or LoopBackData[0] == 0x00:      # -- Read Wakeup(0xF0) data --
                    if LoopBackData[0] == 0x00:
                        self.SerPort.read()
                    LoopBackData[0] = int(ord(self.SerPort.read()))
            else:
                return -1, '!!!Port Error'
        return 0, 0
            
    # -----------------------

    def _KeyBytesDecoder(self, KeyByte1, KeyByte2):
        if KeyByte2 == 0x8F:
            if KeyByte1 == 0xEA or KeyByte1 == 0x6B or KeyByte1 == 0x6E or KeyByte1 == 0xEF:
                CGTvar.KLNdict['HEADER_FORMAT'] = 4       # Format Byte + Target & Source Addresses + Additional Length
            if KeyByte1 == 0xE9 or KeyByte1 == 0x6E:
                CGTvar.KLNdict['HEADER_FORMAT'] = 3         # Format Byte + Target & Source Addresses
            if KeyByte1 == 0xE6 or KeyByte1 == 0x67:
                CGTvar.KLNdict['HEADER_FORMAT'] = 2         # Format Byte + Additional Length
            if KeyByte1 == 0xE5:
                CGTvar.KLNdict['HEADER_FORMAT'] = 1       # Format Byte
        else:
            header_length = 0
            CGTvar.KLNdict[ 'HEADER_FORMAT' ] = 0

