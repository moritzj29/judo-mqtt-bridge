#!/usr/bin/python3
# -*- coding: utf-8 -*-
#-------------------------------------------------------------------------------
#Judo Config
JUDO_USER = "myjudousername"
JUDO_PASSWORD = "myjudopassword"

#MQTT Config
BROKER = "192.168.1.2"              #Broker IP
USE_MQTT_AUTH = True                #Set true, if user/pw authentification on broker, set false, if using anonymous login
USE_MQTT_TLS = False                #Set true, if using TLS/SSL for MQTT connection
MQTTUSER = "mqttuser"               #only required if USE_MQTT_AUTH = True
MQTTPASSWD = "mosquitto"            #only required if USE_MQTT_AUTH = True
PORT = 1883                         #MQTT PORT, 1883 default standard, 8883 if using TLS/SSL

#General Config
LOCATION = "my_location"            #Location of Judo device
STATE_UPDATE_INTERVAL = 20          #Update interval in seconds
AVAILABILITY_ONLINE = "online"
AVAILABILITY_OFFLINE = "offline"

# List of Judo devices, can be extended with more devices
DEVICES = [
    dict(
        LOCATION=LOCATION,
        NAME="Judo_isoftsaveplus" ,         #Name of Judo device
        MANUFACTURER = "ShapeLabs.de",      #CC BY-NC-SA 4.0
        SW_VERSION = "2.0",
        AVAILABILITY_ONLINE = AVAILABILITY_ONLINE,
        AVAILABILITY_OFFLINE = AVAILABILITY_OFFLINE,
        
        # Serial number of the Gateway (not shown in the Judo app but given on the sticker on the gateway)
        # if not given, order in DEVICES is assumed to be the same as in the response from the Judo API
        # can be left empty if only one device is associated with the Judo account
        # associated serial number will be published to the notification topic upon first connection
        # in case of multiple devices, it is highly recommended to set the serial number to ensure correct and consistent matching
        SERIAL_NUMBER = "",
        
        # The maximum slider values that can be set for leakage protection can be limited here. 
        # The limitation can be useful to improve the handling of the sliders in the Homeassistant. 
        LIMIT_EXTRACTION_TIME = 60,          #can setup to max 600min 
        LIMIT_MAX_WATERFLOW = 3000,          #can setup to max 5000L/h 
        LIMIT_EXTRACTION_QUANTITY = 500,     #can setup to max 3000L

        USE_SODIUM_CHECK = True,             #'True' activates the monitoring of the sodium limit when the water hardness is set
        SODIUM_INPUT = 30,                   #Sodium level of input water [mg/L]. Ask your water provider or check providers webpage
        SODIUM_LIMIT = 200,                  #Sodium limit value. Default 200mg/L (Germany)

        #Set this Flag to True, if you've a Judo Softwell P. There are no functions for leakage protection, no battery-,salt- & softwatersensor
        USE_WITH_SOFTWELL_P = False
    ),
    ]
#Error- and warning messages of plant published to notification topic ( LOCATION/NAME/notify ). Can be used for hassio telegram bot..
LANGUAGE = "DE"                     # "DE" / "ENG"
MQTT_DEBUG_LEVEL = 2                # 0=0ff, 1=Judo-Warnings/Errors, 2=Command feedback  3=Script Errors, Exceptions
MAX_RETRIES = 3

#The environment in which the script will run. Select "True" if you want to run it in the Appdeamon, or set "False" if you want to run the script on a generic Linux.
RUN_IN_APPDEAMON = True

#-------------------------------------------------------------------------------

# for Appdaemon the whole path is required "/config/appdaemon/apps/main/temp_getjudo.pkl", otherwise "temp_getjudo.pkl"
if RUN_IN_APPDEAMON == True:
    TEMP_FILE = "/config/apps/main/temp_getjudo.pkl"
else:
    TEMP_FILE = "temp_getjudo.pkl"
