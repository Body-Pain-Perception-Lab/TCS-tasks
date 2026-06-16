#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 20 10:08:29 2023

@author: grunert
"""
from tkinter import *
import os,time
import sys
import serial


hBV = 0
lBV = 0
volt=[100,150,200,250,300,350,400,450,500,550,600,800,700,600,500,400,300,200,100]

# Serial port depends on the operating system:
#   Linux   -> /dev/ttyUSB0
#   Windows -> COM8 (Silicon Labs CP210x USB to UART Bridge)
if sys.platform.startswith('win'):
    DS5_PORT = 'COM8'
else:
    DS5_PORT = '/dev/ttyUSB0'

ser = serial.Serial(DS5_PORT, 19200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)

def voltage(value):
    global hBV,lBV
    tmp=value*2/256
    hBV=int(tmp)
    lBV =int((tmp-hBV)*256)


PW=20 #in ms
tmp=PW*10/256
hBW=int(tmp)
lBW =int((tmp-hBW)*256)
ser.write(bytearray([87, hBW, lBW])) #pulse width
time.sleep(0.01)

ser.write(bytearray([78])) #zeroing PulsCount	
time.sleep(0.01)

ser.write(bytearray([69, 1 ])) #set elektrodennummer
time.sleep(0.01)

ser.write(bytearray([255])) #set elektrodennummer
time.sleep(0.01)

for v in range(0,19): 
    voltage(volt[v])
    ser.write(bytearray([83, hBV, lBV])) #pulse width
    time.sleep(0.005)
    ser.write(bytearray([80]))
    time.sleep(0.5)#zwischen Pulsen Pause 500ms


    
ser.close()