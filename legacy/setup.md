

#Base Code set up 
```
sudo apt-get update
sudo apt-get upgrade
```

**WIfi set up** 
```
sudo nano /etc/wpa_supplicant/wpa_supplicant.conf
```
add  your network network
```
network={
   ssid="{your interent name}"
   psk="{your internet password}"
}
```

**Download this repository**
```
git clone https://github.com/SensorNetwork2020_DashServer_SDS011_DHT22
```

# DHT22 Set up 

Intall the package

```
 'sudo python3  SDS-011-Python-master/AQ/Scripts/DHT/setup.py install'
```

# GPS Set up 
GPS Dongle G-mouse, set up video for setting up the dolge GPS as the RPI3 clock !!!
https://www.youtube.com/watch?v=Oag9qYuhMGg


1st get gps module
```
sudo apt-get install gpsd gpsd-clients python-gps chrony
```
2nd  in terminal 
```
sudo nano /etc/default/gpsd
```
set the following
``` 
START_DAEMON=”true”
USBAUTO=”true”
DEVICES=”/dev/ttyACM0″
GPSD_OPTIONS=”-n”
```
3rd  in the terminal 
```
sudo nano /etc/chrony/chrony.conf
```
Add the following line to the end of the file:

```
refclock SHM 0 offset 0.5 delay 0.2 refid NMEA
```
3rd Reboot the RPI3 ""sudo reboot""

4th  check that both are active in the terminal
```
systemctl is-active gpsd
systemctl is-active chronyd
su
```
5th see the data
```
gpsmon -n
```
