 [English](/README.md)/[日本語](/README-jp.md)
 
# **AQ_Plot_server** ( Data reciver and Plotly Interface and set up details  )
   - **dash_server.py** {Plotly Dash, base sensor network interface}
   - **data_reciver.py** {Flask node data reciver code}
   - **MultiPage**
     - 2 **Dash_GPSmap_server.py** {Plotly Dash, with pages for sensor network and GPS maps}
 
 ## dash_server.py
 #### "plotly dashed" based data plotter (https://plotly.com/dash/)
 ##### Set up: 
 
 Termial commands  update and install the needed software. 
```
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install xsel xclip libxml2-dev libxslt-dev python-lxml python-h5py python-numexpr python-dateutil python-six python-tz python-bs4 python-html5lib python-openpyxl python-tables python-xlrd python-xlwt cython python-sqlalchemy python-xlsxwriter python-jinja2 python-boto python-gflags python-googleapi python-httplib2 python-zmq libspatialindex-dev
sudo pip install bottleneck rtree
sudo apt-get install python-numpy python-matplotlib python-mpltoolkits.basemap python-scipy python-sklearn python-statsmodels python-pandas
pip install flask
pip install codecs
pip install dash
```

data location need to be updated from defult (/home/pi/SDS-011-Python/AQ_run/data/) 
Termianl update comand: 
```
sed -i s/"/home/pi/SDS-011-Python/AQ_run/data/"/"{Data loc}"/g　data_reciver.py 
```

Manual edit comand: 

```
nano data_reciver.py 
```

 ###### Run: 
 ```
python {SaveLoc}/AQ_Plot_server/data_server.py 
 ```
 ###### Decription: 
 
## data_reciver.py
#### "Flask" date reciver. 
##### Set up: 
data location need to be updated from defult (/home/pi/SDS-011-Python/AQ_run/data/) 
Termianl update comand: 

```
sed -i s/"/home/pi/SDS-011-Python/AQ_run/data/"/"{Data loc}"/g　data_reciver.py 
```

Manual edit comand: 
```
nano data_reciver.py 
```

###### Run: 
 sudo python {SaveLoc}/AQ_Plot_server/data_reciver.py
###### Input: 

```
{IP}/data/<nodeinfo>/<nodedata>/ 
```
##### Example: 
```
 {IP}/data/NODE1-Testloc/T,18,RH,80,{Node IP} 
 ```
 
 ###### Run: 
 ```
python {SaveLoc}/AQ_Plot_server.py 
 ```
 After running take note of the ip. Use this for the Nodes https://github.com/JarvisSan22/SensorNetwork2020_DashServer_SDS011_DHT22/tree/main/AQ_nodes
 
 ###### Decription: 
This will create a new file "Testloc_NODE1_YYYYMMDDHHMMSS", if the file aready exist, the new data will append to the file. 
Note as long as the <nodedata> is in a "{column name},{column data}, {column name},{column data},{IP}" format, diffrent types of data can be recived (not just Temp and RH).  
Aditional more than 2 data types can be recived as long as the last 

```python
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

```
