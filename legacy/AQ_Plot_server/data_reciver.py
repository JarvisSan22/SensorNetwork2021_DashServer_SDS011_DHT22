
from __future__ import print_function
import datetime
import os
import sys

sys.path.append(".") #Import varaibles in run from AQ_Plot_server directory 
sys.path.append(sys.path[0][0:sys.path[0].find("AQ_Plot_server")]) #Import varaiblesif run from home directory 

import variables as V

import glob
import time
import csv
from flask import Flask , render_template, send_file, make_response, request
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io
import urllib

import matplotlib.dates as mdates
import datetime 
import psutil # to check the sensors are running 

dataloc=V.DATAFOLDER
IP=V.IP


def createfile(filename,nodename,nodedata,nodeip):
    """
    info
    -Creates new data file with info columns for created time, name, ip
    -Data fromat =["T","20","RH","50"]  data tpye , data , datatype,data .......
    Created:2020/05/17
    
    """
    columns="time,"
    # account for sensors mode
    sencolumns=columns+",".join(nodedata[1::2]) #Data fromat =["Nodetime",1030,"T","20","RH","50"] -> ["nodetime","T","RH"]
    # create new file 
    f = open(filename, 'w+')  # open file
    ts = time.time()
    tnow = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    print("time of creation,"+tnow, file=f)
    # Add sensors information
    print("Node:,"+nodename, file=f)
    # operating sensors
    print('Interval,10',file=f)
    print("IP,"+nodeip,file=f)
    # add columns
    print(sencolumns, file=f)
    # Add first line of data Data fromat =["Nodetime",1030,"T","20","RH","50"] ->   ["1030","20","50"]
    print(tnow+","+",".join(nodedata[2::2]), file=f)
    print("New file created for:"+nodename)
    f.close()


app = Flask(__name__) 
  
#Data Reciver   ---------------------------------------------------------------------
@app.route("/data/<nodeinfo>/<nodedata>")
def recivedata(nodeinfo, nodedata):
    # get time data is recived
    ts = time.time()
    tnow = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    # read the nodename for operation sensors 
    nodedata = nodedata.split(",")
    #print(nodedata)
    #nodedate=list(nodedata)
   #print(nodedata)
    nodedate=[data.decode("utf-8") for data in nodedata]
    print("---------------------------------------------------")
    print("Recived data:"+nodeinfo)
    print(nodedata)
    print("---------------------------------------------------")
    # split up data 
    
    nodeday =  datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")    
    nodename=nodeinfo.split("-")[0]
    nodeip=nodedata[-0] # ip adress at end of the data set
    #Crate file nodename-date.csv
    print(nodeinfo)
    filename = dataloc+nodeinfo+"_"+tnow.split(" ")[0].replace("_","")+".csv"
    print(filename)
    if(not os.path.isfile(filename)):
        print("Create new file")
        createfile(filename,nodename,nodedata,nodeip)
    else:
        ts = time.time()
        tnow = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        f = open(filename, 'a')  # open file
        #print(nodedata)
        print(tnow+","+",".join(nodedata[2::2]), file=f)
        print("Data recived from "+nodename+" at "+tnow)
        print(nodedata)
        f.close()
    #Plot data 
  
    return "Done"




#Reciver Data 

#run 
if __name__ == '__main__':
    print("Reciver IP:",IP,":8090")
    app.run(host=IP, port=8090,debug=True)
