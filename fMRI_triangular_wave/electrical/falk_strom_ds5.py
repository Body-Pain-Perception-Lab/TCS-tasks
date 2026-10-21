#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: grunert
"""
from tkinter import *
import os,time
import serial

root = Tk()

ws = 1920#root.winfo_screenwidth()
hs = 1000#root.winfo_screenheight()-10

root.geometry("%dx%d+%d+%d" % (ws, hs, 0, 40))
root.title('DS5 RECORD')
root.configure(bg='#efe')

ser = serial.Serial('/dev/ttyACM0', 115200, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE)

window = Canvas(root, bg='#efe', height=hs, width=ws) 

Continue = True
Start = False
Stop = False

###################### button event ###################################

def beenden():
    global Continue
    Continue = False

def start():
    global Start,Stop
    Start = True
    Stop  = False

def stop():
    global Stop,Start
    window.itemconfig(1,text="")
    Start = False
    Stop  = True

############################ desktop ##################################

window.create_text(ws/2,hs-300,font=("Arial",144), anchor = CENTER,fill="blue",text="") #Strom numerisch

for v in range(0,5):  window.create_line(0,(v*100)+100,ws,(v*100)+100,fill='silver',width=1) #diagramm

window.create_line(0,0,0,0,fill='red',width=1) #rote trennlinie

for v in range(0,ws): window.create_line(0,0,0,0,fill='blue',width=1) # kurfe

s=10.0
for v in range(0,5): 
    window.create_text(50,(v*100)+80,font=("Arial",14), anchor = CENTER,fill="silver",text=str(s)+"mA")
    s-=2.5
    
btn_exit  = Button(root, text='EXIT', command=beenden);btn_exit.place(x=ws-100, y=hs-70)
btn_start = Button(root, text='START',command=start)  ;btn_start.place(x=ws/2-300,width=200, y=hs-70)
btn_stop  = Button(root, text='STOP', command=stop)   ;btn_stop.place(x=ws/2+100, width=200, y=hs-70)

############################ sub ######################################

def start_record():
    ser.flushInput()  #serbuffer clear
    data=str(ser.readline())
    value_b=data.replace("'","").replace("b","").replace(r"\r\n", r"") #in value befor
    for v in range(0,ws): window.coords(v+7,0, 0, 0, 0)
    averv=0;averc=0
    while Start:
        for v in range(0,ws): 
            data=str(ser.readline())
            value=data.replace("'","").replace("b","").replace(r"\r\n", r"")
            #window.coords(7, v, 10, v, 500)
            window.coords(v+8, v, float(value_b)*(-2.0)+500.0, v+1,  float(value)*(-2.0)+500.0)
            
            #if float(value) > 50:
            window.itemconfig(1,text=str(value))#averc=0;averv=0
                
                #print(value)
            value_b=value
            #if averc<20:averc+=1;averv+=int(value)
            #else:       window.itemconfig(1,text=str(round(averv/2000,2))+"mA");averc=0;averv=0
            window.place(x=0, y=0)
            if not Continue or Stop: return
            root.update()
    
############################ main ####################################

while Continue:
    if Start:start_record()
    root.update()

ser.close()
root.destroy()
