#!/usr/bin/python3
# -*- coding: utf-8 -*-
import urllib3
import json
import sys
import config_getjudo
import messages_getjudo
import hashlib
from paho.mqtt import client as mqtt
from datetime import datetime
import pickle
from threading import Timer
from judo_device import JudoDeviceConfig


class Function_Caller(Timer):
    def run(self):
        while not self.finished.wait(self.interval):  
            self.function()


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(messages_getjudo.debug[1])
        for device in devices:
            client.subscribe(device.command_topic)
        print(messages_getjudo.debug[2])
        
        client.publish(availability_topic, config_getjudo.AVAILABILITY_ONLINE, qos=0, retain=True)

        for device in devices:
            for entity in device.entities:
                entity.send_entity_autoconfig()
            device.notify.send_autoconfig()

        print(messages_getjudo.debug[3])
    else:
        print(messages_getjudo.debug[4].format(rc))


#Callback
def on_message(client, userdata, message):
    print(messages_getjudo.debug[5].format(message.topic, message.payload))
    try:
        for device in devices:
            if message.topic == device.command_topic:
                # relevant device found
                break
        else:
            # ToDo
            device.notify.publish([messages_getjudo.debug[27].format(sys.exc_info()[-1].tb_lineno),e], 3)
        device.on_message(userdata, message)

    except Exception as e:
        device.notify.publish([messages_getjudo.debug[27].format(sys.exc_info()[-1].tb_lineno),e], 3)


def judo_login(username, password):
    pwmd5 = hashlib.md5(password.encode("utf-8")).hexdigest()
    try:
        login_response = http.request('GET', f"https://www.myjudo.eu/interface/?group=register&command=login&name=login&user={username}&password={pwmd5}&nohash=Service&role=customer")
        login_response_json = json.loads(login_response.data)
        if "token" in login_response_json:
            print(messages_getjudo.debug[22].format(login_response_json['token']))
            # update token in all device instances
            for device in devices:
                device.save_data.token = login_response_json['token']
                mydata["devices"][device.SERIAL_NUMBER] = device.save_data
            mydata["token"] = login_response_json['token']
        else:
            for device in devices:
                device.notify.publish(messages_getjudo.debug[21], 2)
            sys.exit()
    except Exception as e:
        for device in devices:
            device.notify.publish([messages_getjudo.debug[28].format(sys.exc_info()[-1].tb_lineno),e], 3)
        sys.exit()


#----- INIT ----
user_agent = {'user-agent':'Mozilla'}
http = urllib3.PoolManager(10, headers=user_agent)

# Create a list of JudoDeviceConfig instances from the configuration
devices: list[JudoDeviceConfig] = []
if len(config_getjudo.DEVICES) > 1:
    # multiple devices -> use a general availability topic (only one possible per MQTT client)
    availability_topic = f"{config_getjudo.LOCATION}/status"
else:
    # only one device -> use the specific availability topic
    availability_topic = f"{config_getjudo.LOCATION}/{config_getjudo.DEVICES[0]['NAME']}/status"
for device_dict in config_getjudo.DEVICES:
    device = JudoDeviceConfig(
        availability_topic=availability_topic,
        MQTT_DEBUG_LEVEL=config_getjudo.MQTT_DEBUG_LEVEL, **device_dict)
    device._http = http
    devices.append(device)

mydata = {"token": 0, "day_today": "", "last_err_id": "", "devices": {}}

# Setting up all entities for homeassistant
for device in devices:
    device.setup_entities()

try: 
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    if config_getjudo.USE_MQTT_AUTH:
        client.username_pw_set(config_getjudo.MQTTUSER, config_getjudo.MQTTPASSWD)
    client.will_set(availability_topic, config_getjudo.AVAILABILITY_OFFLINE, qos=0, retain=True)
    if config_getjudo.USE_MQTT_TLS:
        # default TLS settings require a valid certificate
        client.tls_set()
    client.connect(config_getjudo.BROKER, config_getjudo.PORT, 60)
    client.loop_start()
except Exception as e:
    sys.exit(messages_getjudo.debug[33])

for device in devices:
    device._client = client

#Load stored variables:
print (messages_getjudo.debug[34])
print ("----------------------")
restore = False
try:
    if config_getjudo.RUN_IN_APPDEAMON == True:
        # if running in AppDaemon, use the temp file to store data
        with open(config_getjudo.TEMP_FILE, "rb") as temp_file:
            mydata = pickle.load(temp_file)
    for device in devices:
        try:
            device_data = mydata["devices"][device.SERIAL_NUMBER]
        except KeyError:
            # if the device is not in the stored data, add it with empty data
            mydata["devices"][device.SERIAL_NUMBER] = device.save_data
            restore = True
        try:
            # if there is some error parsing the stored data, reinitialize the device
            device.load_stored_variables(device_data)
        except Exception as e:
            device.notify.publish([messages_getjudo.debug[29].format(sys.exc_info()[-1].tb_lineno),e], 3)
            mydata["devices"][device.SERIAL_NUMBER] = device.save_data
            restore = True

except Exception as e:
    restore = True
    for device in devices:
        device.notify.publish(["General: " + messages_getjudo.debug[29].format(sys.exc_info()[-1].tb_lineno),e], 3)

if restore:
    try:
        if config_getjudo.RUN_IN_APPDEAMON == True:
            with open(config_getjudo.TEMP_FILE,"wb") as temp_file:
                pickle.dump(mydata, temp_file)
            for device in devices:
                device.notify.publish("General: " + messages_getjudo.debug[41], 3)
    except:
        for device in devices:
            device.notify.publish(["General: " + messages_getjudo.debug[42].format(sys.exc_info()[-1].tb_lineno),e], 3)
        sys.exit()

if mydata["token"] == 0:
    judo_login(config_getjudo.JUDO_USER, config_getjudo.JUDO_PASSWORD)


#----- Mainthread ----
def main():
    error_counter = 0
    data_valid = False
    # get device data from Judo server
    try:
        response = http.request('GET',f"https://www.myjudo.eu/interface/?token={mydata["token"]}&group=register&command=get%20device%20data")
        response_json = json.loads(response.data)
        try:
            response_json = json.loads(response.data)
            data_valid = True
        except Exception as e:
            for device in devices:
                device.notify.publish([messages_getjudo.debug[30].format(sys.exc_info()[-1].tb_lineno),str(e) + " - "+ str(response.data)], 3)
            error_counter += 1
        if data_valid == True:
            if response_json["status"] ==  "ok":
                today = datetime.today()
                new_day = False
                if today.day != mydata["day_today"]:
                    mydata["day_today"] = today.day
                    new_day = True
                
                for i, device in enumerate(devices):
                    if device.SERIAL_NUMBER == "":
                        # if no serial number is set, use the order of the devices in the config
                        try:
                            response_data = response_json["data"][i]
                            device.SERIAL_NUMBER = response_data["serialnumber"] # set serial number at least for runtime to ensure consistency
                            device.notify.publish(messages_getjudo.debug[45].format(i+1, device.SERIAL_NUMBER), 1)
                        except IndexError:
                            # relevant device not found in response, skip it
                            continue
                        except IndexError:
                            # If the index is out of range, skip this device
                            continue
                    else:
                        for response_data in response_json["data"]:
                            if response_data["serialnumber"] == device.SERIAL_NUMBER:
                                break
                        else:
                            # relevant device not found in response, skip it
                            continue
                    device.save_data.da = response_data["data"][0]["da"]
                    device.save_data.dt = response_data["data"][0]["dt"]

                    device.update_entities(response_data, new_day)

                    # update mydata with the current device data
                    mydata["devices"][device.SERIAL_NUMBER] = device.save_data

                    print("Publishing parsed values over MQTT....")
                    device.publish_entities()

            elif response_json["status"] == "error":
                error_counter += 1
                if response_json["data"] == "login failed":
                    for device in devices:
                        device.notify.publish(messages_getjudo.debug[23],3)
                    judo_login(config_getjudo.JUDO_USER, config_getjudo.JUDO_PASSWORD)
                else:
                    val = response_json["data"]
                    for device in devices:
                        device.notify.publish(messages_getjudo.debug[24].format(val),3)
            else:
                error_counter += 1
                print(messages_getjudo.debug[25])
    except Exception as e:
        error_counter += 1
        for device in devices:
            device.notify.publish([messages_getjudo.debug[31].format(sys.exc_info()[-1].tb_lineno),e],3)

    # Check for error messages
    data_valid = False
    try:
        error_response = http.request('GET',f"https://myjudo.eu/interface/?token={mydata["token"]}&group=register&command=get%20error%20messages")
        try:
            error_response_json = json.loads(error_response.data)
            data_valid = True
        except Exception as e:
            error_counter += 1
            for device in devices:
                device.notify.publish([messages_getjudo.debug[30].format(sys.exc_info()[-1].tb_lineno),str(e) + " - "+ str(error_response.data)], 3)
        if data_valid == True:
            if error_response_json["data"] != [] and error_response_json["count"] != 0:
                # check if error message is new
                if mydata["last_err_id"] != error_response_json["data"][0]["id"]:
                    mydata["last_err_id"] = error_response_json["data"][0]["id"]

                    timestamp = error_response_json["data"][0]["ts_sort"]
                    timestamp = timestamp[:-7] + ": "

                    # warning
                    if error_response_json["data"][0]["type"] == "w":
                        error_message = timestamp + messages_getjudo.warnings[error_response_json["data"][0]["error"]]
                        for device in devices:
                            if device.SERIAL_NUMBER == error_response_json["data"][0]["serialnumber"]:
                                device.notify.publish(error_message, 1)
                                break
                    # error
                    elif error_response_json["data"][0]["type"] == "e":
                        error_message = timestamp + messages_getjudo.errors[error_response_json["data"][0]["error"]]
                        for device in devices:
                            if device.SERIAL_NUMBER == error_response_json["data"][0]["serialnumber"]:
                                device.notify.publish(error_message, 1)
                                break
    except Exception as e:
        error_counter += 1
        for device in devices:
            device.notify.publish([messages_getjudo.debug[30].format(sys.exc_info()[-1].tb_lineno),e], 3)

    try:
        if config_getjudo.RUN_IN_APPDEAMON == True:
            with open(config_getjudo.TEMP_FILE,"wb") as temp_file:
                pickle.dump(mydata, temp_file)
    except Exception as e:
        error_counter += 1
        for device in devices:
            device.notify.publish([messages_getjudo.debug[29].format(sys.exc_info()[-1].tb_lineno),e], 3)

    if error_counter >= config_getjudo.MAX_RETRIES:
        for device in devices:
            device.notify.publish(messages_getjudo.debug[32].format(config_getjudo.MAX_RETRIES),1)
        sys.exit()
#---------------------

Function_Caller(config_getjudo.STATE_UPDATE_INTERVAL, main).start()

for device in devices:
    device.notify.publish(messages_getjudo.debug[39], 2)   #Init Complete
