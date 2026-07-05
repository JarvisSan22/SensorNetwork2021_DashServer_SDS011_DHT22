# -*- coding: utf-8 -*-
"""
Created on 2021/09/18
@author: Daniel Jarvis
"""

import os 
import socket 
#Basesettings
os.getcwd()

#DATAFOLDER=os.path.join(".","AQ_run","data","")
#RUNFOLDER=os.path.join(".","AQ_run","Scripts","") 
DATAFOLDER=r"C:\Users\jarvi\Documents\PythonScripts\SensorNetwork2021_DashServer_SDS011_DHT22\AQ_run\data"
RUNFOLDER=r"C:\Users\jarvi\Documents\PythonScripts\SensorNetwork2021_DashServer_SDS011_DHT22\AQ_run\Scripts"



#r"C:\Users\jarvi\Documents\PythonScripts\SensorNetwork2021_DashServer_SDS011_DHT22\AQ_run\Scripts"
SERVERFOLDER=""
DEVICERAN="RPI"
#LOC=['Location Name','lat', 'lon'] 
LOC=['Home','', ''] 

#Server display settings "single":Just time series . "multi" Time series and GPS map
Type="multi"
TimeSeries=False #True date range select #False Single data file select 
GPSMAPLOC=r"C:\Users\jarvi\Documents\PythonScripts\SensorNetwork2021_DashServer_SDS011_DHT22\AQ_Plot\GPS_MAP.html"


#Check internet connect, URL to ping
URL = 'https://github.com/JarvisSan22/SensorNetwork2021_DashServer_SDS011_DHT22'
######Setting to run sensors of home unit#######
#Data record period(in seconds)
integration=10
#MODE LOG: logs data, new file every day #GPS add lat, long, alt to data if GPS is added #TEST create a new data file ever time scrip is run (GPS does the same as well)
MODE="LOG"  
#Note if GPS is "ON" ,it takes up "/dev/ttyACM0" port


##Desired Pollution sensors to run  (OPCN2 or 2 and SDS011)
##大気汚染の観測器を無効する
OPCON="ON"

RUNSEN=["SDS011_1"]  #add your SDS011 name, if you have more then 1 sds attaced, add the other name to the array  i.e RUNSEN=["SDS011_1,SDS011_2"]

#Sensor ports for deried sensors, if you dont know check the /dev folder
#センサーの接続したポート
RUNPORT=["/dev/ttyUSB0"] #for multipe SDS011 add a "/dev/ttyUSB#" #=number to this array

#Temp sensors port number, if a DHT11 or 22 is running get the por  
#DHTという温湿度計の設定
DHTON="ON"
DHTNAMES=["DHT22_1"]
DHTPINS=[14] #check the pin

#Light settings  #LEDの設定
LIGHT="OFF" #LEDS option 
LIGHTPIN=[]
BLINKT="OFF"  #BLINkt hat option (Cant fit DHT22 with the BLINKET Hat)
PMVALUE=[10,20,30]  #Set intevals for light colors 

#IP SETTINGS 
# ホスト名を取得 #Get host name 
host = socket.gethostname()
# ipアドレスを取得, #Get ip 
IP = socket.gethostbyname(host)
PORT=8888
