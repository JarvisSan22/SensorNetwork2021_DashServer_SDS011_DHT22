from __future__ import print_function
import datetime
import os
import sys
import glob
import time
import csv
from flask import Flask , render_template, send_file, make_response, request, url_for

import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure
import io
import urllib

import matplotlib.dates as mdates
import datetime 
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import threading

sys.path.append("..") #Import varaibles in run from AQ_Plot_server directory 
#sys.path.append(sys.path[0][0:sys.path[0].find("AQ_run")]) #Import varaiblesif run from home directory
import variables as V #IMport the file names, you dont want to type them out



def convertList(l):
    newlist = []
    for x in l:
        templ = [item.encode('UTF8') for item in x]
        newlist.append(templ)
    return newlist


def dateparse(timestamp):  # read the data time properly deal with the annoying wronge date issue
    time = pd.to_datetime(timestamp, yearfirst=True, dayfirst=False)
 #   print(time)
  #  time.strftime(time, '%Y-%m-%d %H:%M:%S')
    return time


def StatusBox(Sen,num,Status,Latest,color):
  print('<p>'+Latest+'</p>')
  temp="""  
    <div class='col"""+num+"""' style='background-color:"""+color+"""'>
        <label for='field1"""+num+"""'>"""+Sen+"""("""+status+""")</label>
        
    </div>     
  """
  
  return temp
  
def StatueBoxes(dataset):
  BoxArray=[]
  i=0
  for node in dataset.keys():
    status="Not Active"
    color="red"
    if "GPS" not in node.upper():
      i+=1
      print("Key -------",dataset.keys())
      df=dataset[node]
      latestdata=df.tail(1)
      #print(latestdata)
      latestdatastr=''
      for c,v in zip(latestdata.columns,latestdata.values[0]):
          if len(c.split("."))>1:
            pass
          else:
            latestdatastr+=c+":"+str(v)
            
      print(latestdatastr)
      today=datetime.datetime.now()
      checktime=today-datetime.timedelta(minutes= 10)
      LastestSenTime=latestdata.index
      print("---LST",LastestSenTime[0])
      if LastestSenTime[0]>checktime:
          status="Active"
          color="green"
          
          
      Box=StatusBox(node,i,status,latestdatastr,color)
      BoxArray.append(Box)
  
  #Sort Box array into one html block
  Nbox=len(BoxArray)
  newrow="NO"
  html="<div style='width: 200px;float: left;'>" #Start block
  for N in range(Nbox):
      if newrow=="YES":
          html+="<div style='width: 200px;float: left;'>" #add new row 
          newrow="NO"
      html+=Nbox[N]
      if N % 3 ==0: #if bivisable by 3 add new colums after row 
        html+=("</div>")
        newrow="YES"
        
  html+="</div>" #end block
  return StatusBoxs    
    

def getdate(loc):
  #Get data files 
  datafile=glob.glob(loc+"****.csv")
  #Get dates 
  dates=list(d.split("-")[1] for d in datafile)
  #convert to datetime
  dates.sort()
  return dates
  
def getdata(loc):
    
  #Get data files
  print("Date get ",loc) 
  datafiles=glob.glob(loc+"****.csv")
  #print(datafiles)
  #Get nodes 
  nodes=list(d.split("/")[~0].split("_")[0] for d in datafiles)
  nodes=list(dict.fromkeys(nodes))
  #print(nodes)
  Dataset={}
  columnsoptions=[]
  badcols=[]
  days=[]
  for node in nodes:
      print('Node;',node)
      data=pd.DataFrame()
      for file in datafiles:
          if node in file.split("/")[~0]:
             dataloop = pd.read_csv(file, header=4, error_bad_lines=False, engine='python',index_col=False)
             if "SDS" in file.split("/")[~0]:
              # print(dataloop.tail(2))
             #  print(file.split("/")[~0])
            #   print(dataloop.columns)
               badcols.append("sds-ExtraData")
               
             for col in list(dataloop.columns):
               if col not in columnsoptions:
                 if col not in badcols:
                   if "TIME" not in col.upper(): #Skip Time 
                     #  print(col.split("."))
                       #print(col)
                       if len(col.split("."))<3: #Skip IP
                         #print(col)
                         columnsoptions.append(col)
                         print(columnsoptions)
                       else:
                         badcols.append(badcols)
                         
                         
             data=pd.concat([data,dataloop],axis=0,sort=True)
     # print(data)
      data.index=dateparse(data.time)
      #print(data.index.date)
      datadays=data.groupby(by=data.index.date).count()
      #datadays=datadays.groups()
      datadays=datadays.index
      #print(datadays)
      for day in datadays:        
            days.append(day)
      Dataset[node]=data #.sort_index()
 # print(days)
  days=set(days)
  days=sorted(days)
  #print(days)
  #print(days)
  #days=list([d.strftime("%Y-%m-%d") for d in days])
  #print(days)
  print(columnsoptions)
  return Dataset,columnsoptions,days

def UpdateData(loc,Datasets,columnsoptions,days):
  print("Update data ",loc) 
  datafiles=glob.glob(loc+"****.csv")
  today=datetime.date.today().strftime('%Y-%m-%d')
  selectfiles=[]
  for tfile in datafiles:
    if today in tfile:
      selectfiles.append(tfile)
    #  print(tfile)
      
 # datafiles=list(if today in f for f in datafiles)
  #print(selectfiles)
  
  #get nodes 
  nodes=list(d.split("/")[~0].split("_")[0] for d in selectfiles)
  nodes=list(dict.fromkeys(nodes))
  
  badcols=[] #bad data columns dic 
  #print(Datasets.keys())
  for node in nodes:
    if node in list(Datasets.keys()): #old node
      data=Datasets[node]
    else: #newnode
      data=pd.DataFrame()
        
    for tfile in selectfiles:
        if node in tfile.split("/")[~0]:
           dataloop = pd.read_csv(tfile, header=4, error_bad_lines=False, engine='python',index_col="time",parse_dates=True)
           if "SDS" in tfile.split("/")[~0]:
            # print(tfile.split("/")[~0])
            # print(dataloop.columns)
             badcols.append("sds-ExtraData")
            # print(dataloop.tail(1))
           
           for col in list(dataloop.columns):
             if col not in columnsoptions:
               if col not in badcols:
                 if "TIME" not in col.upper(): #Skip Time 
                   #  print(col.split("."))
                     #print(col)
                     if len(col.split("."))<3: #Skip IP
                       print("New col:",col)
                       columnsoptions.append(col)
                       #print(columnsoptions)
                     else:
                       badcols.append(badcols)
                       
                
           data=pd.concat([data,dataloop],axis=0)
    #print(data.index)
    #data.index=pd.to_datetime((data.index))
    #print(data.index.date)
    #print(data.index[0])
    #print(data.tail(4))
    datadays=data.groupby(by=data.index.date).count()
    
    #datadays=datadays.groups()
    datadays=datadays.index
    #print(datadays)
    for day in datadays:        
      days.append(day)
    Datasets[node]=data #.sort_index()
 #print(days)
  days=set(days)
  days=sorted(days)
  #print(days)
  #print(days)
  #days=list([d.strftime("%Y-%m-%d") for d in days])
  #print(days)
  #print(columnsoptions)
  return Datasets,columnsoptions,days
  
def BaseLayout(days,valoptions,columns):
    Base=html.Div([
    dcc.DatePickerRange(
        id='day-picker',
        start_date=days[~0],
        end_date=days[~0],
        min_date_allowed=days[0],
        max_date_allowed=days[~0]+datetime.timedelta(days=1),
        display_format='D MMM YYYY'
    ),
    dcc.Dropdown(id="val-select",
    options=valoptions,
    value=columns[0] 
    ),
    dcc.Graph(id='graph-with-slider'), 
   # dcc.Markdown(children=StatusBox),
    ])
    return Base



class ThreadingTest(object):
    """ Threading example class
    The run() method will be started and it will run in the background
    until the application exits.
    """

    def __init__(self, interval=3600):
        """ Constructor
        :type interval: int
        :param interval: Check interval, in seconds
        """
        self.interval = interval

        thread = threading.Thread(target=self.run, args=())
        thread.daemon = True                            # Daemonize thread
        thread.start()                                  # Start the execution

    def run(self):
        """ Method that runs forever """
        now=datetime.date.today()
        while True:
            # Do something
            #print(today)
            if now!=today: #New Day
              print("Newday ",now," Yesterday ", today)
              today=now
              today=datetime.date.today()
              print(today)
        #      global today
              #Get Data First Iteraction
              Dataset,columns,days=getdata(dataloc)
              #global Dataset
           #   global days
              #Create Val select option dicts 
              valoptions=[]
              for val in columns:
                  valoptions.append({"label":val,"value":val})
              #print(valoptions)
              #StatusBox=StatueBoxes(Dataset) Error
              app.layout = BaseLayout(days,valoptions,columns)


#print(days[0],days[~0])
#Create Dash app

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)


dataloc=V.DATAFOLDER+"/" #"/home/pi/SDS-011-Python/AQ_run/data/"
today=datetime.date.today()
print(today)
#global today
#Get Data First Iteraction
Dataset,columns,days=getdata(dataloc)
#global Dataset
#global days
#Create Val select option dicts 
valoptions=[]
for val in columns:
    valoptions.append({"label":val,"value":val})
#print(valoptions)
#StatusBox=StatueBoxes(Dataset) Error

app.layout = BaseLayout(days,valoptions,columns)
ThreadingTest()




@app.callback(
    Output('graph-with-slider', 'figure'),
    [Input('day-picker', 'start_date'),Input('day-picker', 'end_date'),Input('val-select',"value")],
    )    
def update_figure(start_day,end_day,val):
    print("Plot date range:",start_day,":",end_day)
    #Dataset,columns,days=getdata(dataloc)
    dataset,columnsoptions,days=UpdateData(dataloc,Dataset,columns,days)
    #global days
    traces = []
    #val="DHT-T"
    for loc, df in dataset.items():
       # print(selected_day)
      #  sday=datetime.datetime.strptime(selected_day,"%Y-%m-%d")
        #print(df[sday])
        if val in list(df.columns):
          
          filtered_df = df[start_day:end_day]
          filtered_df=filtered_df.resample("1min").mean()
          traces.append(dict(
           x=filtered_df.index,
           y=filtered_df[val],
           text=loc,
           mode='markers',
           opacity=1,
           marker={
              'size': 5,
              'line': {'width': 0.5, 'color': 'white'}
           },
           name=loc
          ))
    #Create axis range
    if "RH" in val.upper():
        ran=[0,100]
        
    else:
        ran=[0,30]
        if filtered_df[val].max()>30:
          ran=[0,50]
        elif filtered_df[val].max()>50:
          ran=[0,70]
          
    #print(traces)
    Dataset=dataset
    #global Dataset

    return {
        'data': traces,
        'layout': dict(
            yaxis={ 'title': val,"range":ran},
            xaxis={'title': 'time'},
            margin={'l': 40, 'b': 40, 't': 10, 'r': 10},
            legend={'x': 0, 'y': 1},
            hovermode='closest',
            transition = {'duration': 500},
        )
    }
   
if __name__ == '__main__':
    

    app.run_server(debug=True,host=V.IP,port=V.PORT)



