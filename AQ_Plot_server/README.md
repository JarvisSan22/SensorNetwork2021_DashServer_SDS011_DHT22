 [English](/README.md)/[日本語](/README-jp.md)
 
# **AQ_Plot_server** ( Data reciver and Plotly Interface, see this reposity for set up details  )
   - **dash_server.py** {Plotly Dash, base sensor network interface}
   - **data_reciver.py** {Flask node data reciver code}
   - **MultiPage**
     - 2 **Dash_GPSmap_server.py** {Plotly Dash, with pages for sensor network and GPS maps}
 
## Data_reciver.py
"Flask" date reciver. \ 
Inputs \
{IP}/data/<nodeinfo>/<nodedata>/ \
Example; \
 {IP}/data/NODE1-Testloc/T,18,RH,80,{Node IP} \
This will create a new file "Testloc_NODE1_YYYYMMDDHHMMSS", if the file aready exist, the new data will append to the file. \
Note as long as the <nodedata> is in a "{column name},{column data}, {column name},{column data},{IP}" format, diffrent types of data can be recived (not just Temp and RH). \
Aditional more than 2 data types can be recived as long as the last \

'''Python
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

'''