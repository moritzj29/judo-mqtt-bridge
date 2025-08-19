import json
import math
import sys
import time
import re
from dataclasses import dataclass, field
import messages_getjudo

@dataclass
class JudoDeviceSafeData:
    day_today = 0
    offset_total_water = 0
    last_err_id = 0
    token = 0
    water_yesterday = 0
    da = 0
    dt = 0
    serial = 0
    reg_mean_time = 0
    reg_mean_counter = 1
    reg_last_val = 0
    reg_last_timestamp = 0
    total_softwater_at_reg = 0
    total_hardwater_at_reg = 0

@dataclass
class JudoDeviceConfig:
    """Configuration for a single Judo device."""
    LOCATION: str
    NAME: str
    MANUFACTURER: str
    SW_VERSION: str
    SERIAL_NUMBER: str
    AVAILABILITY_ONLINE: str
    AVAILABILITY_OFFLINE: str
    USE_SODIUM_CHECK: bool
    SODIUM_INPUT: int
    SODIUM_LIMIT: int
    LIMIT_EXTRACTION_TIME: int
    LIMIT_MAX_WATERFLOW: int
    LIMIT_EXTRACTION_QUANTITY: int
    USE_WITH_SOFTWELL_P: bool
    MQTT_DEBUG_LEVEL: int  # Debug level for MQTT messages
    availability_topic: str

    # not set at initialization
    entities: list['Entity'] = field(default_factory=lambda: [])
    notify: 'NotificationEntity | None' = None  # Notification entity for errors and warnings
    _http: any  = None # HTTP client, e.g., urllib3.PoolManager()
    _client: any  = None # MQTT client, e.g., paho.mqtt.client.Client()

    save_data: JudoDeviceSafeData = field(default_factory=JudoDeviceSafeData)

    @property
    def command_topic(self):
        return f"{self.LOCATION}/{self.NAME}/command"

    @property
    def state_topic(self):
        return f"{self.LOCATION}/{self.NAME}/state"
    
    @property
    def notification_topic(self):
        return f"{self.LOCATION}/{self.NAME}/notify"
    
    @property
    def client_id(self):
        return f"{self.NAME}-{self.LOCATION}"
    
    @property
    def entity_device_config(self):
        return {
            "identifiers": f"[{self.client_id}]",
            "manufacturer": self.MANUFACTURER,
            "model": self.NAME,
            "name": self.client_id,
            "sw_version": self.SW_VERSION
        }
    
    @property
    def entity_config(self):
        return {
            "device": self.entity_device_config,
            "availability_topic": self.availability_topic,
            "payload_available": self.AVAILABILITY_ONLINE,
            "payload_not_available": self.AVAILABILITY_OFFLINE,
        }

    def entity(self, name, icon, entity_type, unit="", minimum=1, maximum=100, step=1, value=0):
        e = Entity(self, name, icon, entity_type, unit, minimum, maximum, step, value)
        self.entities.append(e)
        return e

    def setup_entities(self):
        #Setting up all entities for homeassistant
        self.next_revision = self.entity(messages_getjudo.entities[0], "mdi:account-wrench", "sensor", "Tagen")
        self.total_water = self.entity(messages_getjudo.entities[1], "mdi:water-circle", "total_increasing", "m³")
        self.output_hardness = self.entity(messages_getjudo.entities[6], "mdi:water-minus", "number", "°dH", 1, 15)
        self.input_hardness = self.entity(messages_getjudo.entities[7], "mdi:water-plus", "sensor", "°dH")
        self.water_flow = self.entity(messages_getjudo.entities[8], "mdi:waves-arrow-right", "sensor", "L/h")
        self.batt_capacity = self.entity(messages_getjudo.entities[9], "mdi:battery-50", "sensor", "%")
        self.regenerations = self.entity(messages_getjudo.entities[10], "mdi:water-sync", "sensor")
        self.water_lock = self.entity(messages_getjudo.entities[11], "mdi:pipe-valve", "switch")
        self.regeneration_start = self.entity(messages_getjudo.entities[12], "mdi:recycle-variant", "switch")
        self.water_today = self.entity(messages_getjudo.entities[14], "mdi:chart-box", "sensor", "L")
        self.water_yesterday = self.entity(messages_getjudo.entities[15], "mdi:chart-box-outline", "sensor", "L")
        
        self.h_since_last_reg = self.entity(messages_getjudo.entities[21], "mdi:water-sync", "sensor", "h")
        self.avg_reg_interval = self.entity(messages_getjudo.entities[22], "mdi:water-sync", "sensor", "h")


        if self.USE_WITH_SOFTWELL_P == False:
            self.salt_stock = self.entity(messages_getjudo.entities[4], "mdi:gradient-vertical", "number", "kg", 1, 50)
            self.salt_range = self.entity(messages_getjudo.entities[5], "mdi:chevron-triple-right", "sensor", "Tage")
            self.total_softwater_proportion = self.entity(messages_getjudo.entities[2], "mdi:water-outline", "total_increasing", "m³")
            self.total_hardwater_proportion = self.entity(messages_getjudo.entities[3], "mdi:water", "total_increasing", "m³")
            self.water_flow = self.entity(messages_getjudo.entities[8], "mdi:waves-arrow-right", "sensor", "L/h")
            self.batt_capacity = self.entity(messages_getjudo.entities[9], "mdi:battery-50", "sensor", "%")
            self.water_lock = self.entity(messages_getjudo.entities[11], "mdi:pipe-valve", "switch")
            self.sleepmode = self.entity(messages_getjudo.entities[13], "mdi:pause-octagon", "number", "h", 0, 10)
            self.extraction_time = self.entity(messages_getjudo.entities[17], "mdi:clock-alert-outline", "number", "min", 10, self.LIMIT_EXTRACTION_TIME, 10)
            self.max_waterflow = self.entity(messages_getjudo.entities[18], "mdi:waves-arrow-up", "number", "L/h", 500, self.LIMIT_MAX_WATERFLOW, 500)
            self.extraction_quantity = self.entity(messages_getjudo.entities[19], "mdi:cup-water", "number", "L", 100, self.LIMIT_EXTRACTION_QUANTITY, 100)
            self.holidaymode = self.entity(messages_getjudo.entities[20], "mdi:palm-tree", "select", messages_getjudo.holiday_options)
            self.mixratio = self.entity(messages_getjudo.entities[23], "mdi:tune-vertical", "sensor", "L")

        self.notify = NotificationEntity(self,messages_getjudo.entities[16], "mdi:alert-outline")

    def load_stored_variables(self, stored_data: JudoDeviceSafeData):
        print (messages_getjudo.debug[35].format(stored_data.last_err_id))
        print (messages_getjudo.debug[36].format(stored_data.water_yesterday))
        self.water_yesterday.value = stored_data.water_yesterday
        print (messages_getjudo.debug[37].format(stored_data.offset_total_water))
        print (messages_getjudo.debug[38].format(stored_data.day_today))
        print ("da: {}".format(stored_data.da))
        print ("dt: {}".format(stored_data.dt))
        print ("serial: {}".format(stored_data.serial))
        print ("token: {}".format(stored_data.token))
        print ("avergage regeneration interval: {}h".format(stored_data.reg_mean_time))
        print ("counter for avg-calc: {}".format(stored_data.reg_mean_counter))
        print ("last regenerations count: {}".format(stored_data.reg_last_val))
        print ("timestamp of last regeneration: {}s".format(stored_data.reg_last_timestamp))
        if self.USE_WITH_SOFTWELL_P == False:
            print ("Softwater prop. since Regeneration: {}L".format(stored_data.total_softwater_at_reg))
            print ("Hardwater prop. since Regeneration: {}L".format(stored_data.total_hardwater_at_reg))

        self.avg_reg_interval.value = stored_data.reg_mean_time

    def update_entities(self, response_json, new_day: bool):
        try:
            # Software version
            val = response_json["data"][0]["data"]["1"]["data"]
            if val != "":
                minor = int.from_bytes(bytes.fromhex(val[2:4]), byteorder='little')
                major = int.from_bytes(bytes.fromhex(val[4:6]), byteorder='little')
                print("Software version: {}.{:02d}".format(major, minor))
            # Hardware version
            val = response_json["data"][0]["data"]["2"]["data"]
            if val != "":
                minor = int.from_bytes(bytes.fromhex(val[0:2]), byteorder='little')
                major = int.from_bytes(bytes.fromhex(val[2:4]), byteorder='little')
                print("Hardware version: {}.{:02d}".format(major, minor))
            # Serial number
            val = response_json["data"][0]["data"]["3"]["data"]
            if val != "":
                val = int.from_bytes(bytes.fromhex(val[0:8]), byteorder='little')
                print("Gerätenummer: {}".format(val))

            self.next_revision.parse(response_json, 7, 0, 4)
            if self.USE_WITH_SOFTWELL_P == False:
                total_water_temp = self.total_water.value * 1000
                self.total_water.parse(response_json, 8, 0, 8)
                if self.total_water.value < total_water_temp:
                    self.notify.publish("Correction made - new value = "+str(total_water_temp)+" - wrong value = "+str(self.total_water.value),3)
                    self.total_water.value = total_water_temp
                self.salt_stock.parse(response_json,94, 0, 4)
                self.salt_range.parse(response_json,94, 4, 8)
                self.total_softwater_proportion.parse(response_json, 9, 0, 8)
                self.water_flow.parse(response_json, 790, 34, 38)
                self.batt_capacity.parse(response_json, 93, 6, 8)
                self.water_lock.parse(response_json, 792, 2, 4)
                self.sleepmode.parse(response_json,792, 20, 22)
                self.max_waterflow.parse(response_json, 792, 26, 30)
                self.extraction_quantity.parse(response_json, 792, 30, 34)
                self.extraction_time.parse(response_json, 792, 34, 38)
                self.holidaymode.parse(response_json,792, 38, 40)
            else:
                self.total_water.parse(response_json, 9, 0, 8)

            self.output_hardness.parse(response_json, 790, 18, 20)
            self.input_hardness.parse(response_json, 790, 54, 56)
            self.regenerations.parse(response_json, 791, 62, 66)
            self.regeneration_start.parse(response_json, 791, 2, 4)

            self.next_revision.value = int(self.next_revision.value/24)   #Calculation hours to days
            self.total_water.value =float(self.total_water.value/1000) # Calculating from L to m³

            if self.USE_WITH_SOFTWELL_P == False:
                if self.holidaymode.value == 3:      #mode1
                    self.holidaymode.value = messages_getjudo.holiday_options[2]
                elif self.holidaymode.value == 5:    #mode2
                    self.holidaymode.value = messages_getjudo.holiday_options[3]
                elif self.holidaymode.value == 9:    #lock
                    self.holidaymode.value = messages_getjudo.holiday_options[1]
                else:                           #off
                    self.holidaymode.value = messages_getjudo.holiday_options[0]

                self.total_softwater_proportion.value = float(self.total_softwater_proportion.value/1000)# Calculating from L to m³
                self.total_hardwater_proportion.value = round((self.total_water.value - self.total_softwater_proportion.value),3)
                self.salt_stock.value /= 1000
                if self.water_lock.value > 1:
                    self.water_lock.value = 1

            self.regeneration_start.value &= 0x0F
            if self.regeneration_start.value > 0:
                self.regeneration_start.value = 1
            
            if new_day:
                    # mydata.day_today = today.day
                    self.save_data.offset_total_water = int(1000*self.total_water.value)
                    self.water_yesterday.value = self.water_today.value
                    self.save_data.water_yesterday = self.water_today.value
            self.water_today.value = int(1000*self.total_water.value) - self.save_data.offset_total_water

            #Hours since last regeneration / Average regeneration interval
            if self.regenerations.value > self.save_data.reg_last_val:
                if (self.regenerations.value - self.save_data.reg_last_val) == 1: #Regeneration has started, 
                    if self.save_data.reg_last_timestamp != 0:
                        self.h_since_last_reg.value = math.ceil((int(time.time()) - self.save_data.reg_last_timestamp)/3600)
                        #neuer_mittelwert = ((counter-1)*alter_mittelwert + neuer_wert)/counter
                        self.avg_reg_interval.value = math.ceil(((self.save_data.reg_mean_counter-1)*self.save_data.reg_mean_time + self.h_since_last_reg.value)/self.save_data.reg_mean_counter)
                        self.save_data.reg_mean_time = self.avg_reg_interval.value
                        self.save_data.reg_mean_counter += 1
                    self.save_data.reg_last_timestamp = int(time.time()) 
                    self.save_data.reg_last_val = self.regenerations.value
                    if self.USE_WITH_SOFTWELL_P == False:
                        self.save_data.total_softwater_at_reg = self.total_softwater_proportion.value
                        self.save_data.total_hardwater_at_reg = self.total_hardwater_proportion.value
                else:
                    self.save_data.reg_last_val = self.regenerations.value
            if self.save_data.reg_last_timestamp != 0:
                self.h_since_last_reg.value = int((int(time.time()) - self.save_data.reg_last_timestamp)/3600)
            
            #Mix ratio Soft:Hard since last regeneration
            if self.USE_WITH_SOFTWELL_P == False:
                softwater_since_reg = self.total_softwater_proportion.value - self.save_data.total_softwater_at_reg
                hardwater_since_reg = self.total_hardwater_proportion.value - self.save_data.total_hardwater_at_reg
                if softwater_since_reg != 0 and hardwater_since_reg !=0:
                    totalwater_since_reg = softwater_since_reg +  hardwater_since_reg

                    if hardwater_since_reg < softwater_since_reg:
                        self.mixratio.value = "1:" + str(round(1/(hardwater_since_reg/totalwater_since_reg),2))
                    else:
                        self.mixratio.value = str(round(1/(softwater_since_reg/totalwater_since_reg),2)) + ":1"
                else:
                    self.mixratio.value = "unknown"
        except Exception as e:
            # log error already here to get correct line number
            self.notify.publish([messages_getjudo.debug[31].format(sys.exc_info()[-1].tb_lineno),e],3)
            raise e

    def publish_entities(self):
        #Publish all entities to homeassistant
        outp_val_dict = {}
        for entity in self.entities:
            outp_val_dict[entity.name] = str(entity.value)
        publish_json(self._client, self.state_topic, outp_val_dict)

    def send_command(self, index, data):
        try:
            # ToDo: make device specific
            cmd_response = self._http.request('GET', f"https://www.myjudo.eu/interface/?token={self.save_data.token}&group=register&command=write%20data&serial_number={self.SERIAL_NUMBER}&dt={self.save_data.dt}&index={index}&data={data}&da={self.save_data.da}&role=customer")
            cmd_response_json = json.loads(cmd_response.data)
            if "status" in cmd_response_json:
                if cmd_response_json["status"] == "ok":
                    return True
        except Exception as e:
            self.notify.publish([messages_getjudo.debug[27].format(sys.exc_info()[-1].tb_lineno),e], 3)
            return False
        return False

    def int_to_le_hex(self, integer, length):
        if length == 16:
            tmp = "%0.4X" % integer
            return (tmp[2:4] + tmp[0:2])
        elif length == 8:
            return ("%0.2X" % integer)
        else:
            self.notify.publish(messages_getjudo.debug[20], 3)

    def on_message(self, userdata, message):
        try:
            command_json = json.loads(message.payload)
            
            if self.output_hardness.name in command_json:
                if self.USE_SODIUM_CHECK == True:
                    sodium = round(((self.input_hardness.value - command_json[self.output_hardness.name]) * 8.2) + self.SODIUM_INPUT,1)
                    if  sodium < self.SODIUM_LIMIT:
                        if self.send_command(str(60), self.int_to_le_hex(command_json[self.output_hardness.name], 8)):
                            self.notify.publish(messages_getjudo.debug[43].format(sodium, self.SODIUM_LIMIT, command_json[self.output_hardness.name]), 2)
                    else:
                        limited_hardness = self.input_hardness.value - ((self.SODIUM_LIMIT - self.SODIUM_INPUT)/8.2)
                        limited_hardness = math.ceil(limited_hardness) #round up
                        if self.send_command(str(60), self.int_to_le_hex(limited_hardness, 8)):
                            self.notify.publish(messages_getjudo.debug[44].format(limited_hardness), 2)
                else:
                    self.set_value(self.output_hardness, 60, command_json[self.output_hardness.name], 8)
            elif self.regeneration_start.name in command_json:
                    self.start_regeneration()


            if self.USE_WITH_SOFTWELL_P == False:
                if self.salt_stock.name in command_json:
                    self.set_value(self.salt_stock, 94,command_json[self.salt_stock.name]*1000, 16)
                
                elif self.water_lock.name in command_json:
                    self.set_water_lock(command_json[self.water_lock.name])


                elif self.sleepmode.name in command_json:
                    self.set_sleepmode(command_json[self.sleepmode.name])

                elif self.max_waterflow.name in command_json:
                    self.set_value(self.max_waterflow, 75, command_json[self.max_waterflow.name], 16)

                elif self.extraction_time.name in command_json:
                    self.set_value(self.extraction_time, 74, command_json[self.extraction_time.name], 16)

                elif self.extraction_quantity.name in command_json:
                    self.set_value(self.extraction_quantity, 76, command_json[self.extraction_quantity.name], 16)

                elif self.holidaymode.name in command_json:
                    self.set_holidaymode(command_json[self.holidaymode.name])

        except Exception as e:
            self.notify.publish([messages_getjudo.debug[27].format(sys.exc_info()[-1].tb_lineno),e], 3)

    def set_water_lock(self, pos):
        if pos < 2:
            pos_index = str(73 - pos)
            if self.send_command(pos_index, ""):
                self.notify.publish(messages_getjudo.debug[7].format(pos), 2)
        else:
            print(messages_getjudo.debug[9])


    def set_sleepmode(self, hours):
        if hours == 0:
            if self.send_command("73", ""):
                self.notify.publish(messages_getjudo.debug[10], 2)
        else:
            if self.send_command("171", str(hours)):
                self.notify.publish(messages_getjudo.debug[12].format(hours), 2)
            if self.send_command("171", ""):
                self.notify.publish(messages_getjudo.debug[14], 2)


    def set_holidaymode(self, mode):
        if mode == messages_getjudo.holiday_options[1]:      #lock
            self.send_command("77", "9")
        elif mode == messages_getjudo.holiday_options[2]:    #mode1
            self.send_command("77", "3")
        elif mode == messages_getjudo.holiday_options[3]:    #mode2
            self.send_command("77", "5")
        else:                                               #off
            if self.send_command("73", ""):
                self.notify.publish(messages_getjudo.debug[40], 1)
            self.send_command("77", "0")


    def start_regeneration(self):
        if self.send_command("65", ""):
            self.notify.publish(messages_getjudo.debug[16], 2)


    def set_value(self, obj, index, value, length):
        if self.send_command(str(index), self.int_to_le_hex(value, length)):
            self.notify.publish(messages_getjudo.debug[18].format(obj.name, value), 2)


class Entity():
    def __init__(self, device: JudoDeviceConfig, name, icon, entity_type, unit = "", minimum = 1, maximum = 100, step = 1, value = 0):
        self.device = device
        self.name = name
        self.unit = unit
        self.icon = icon
        self.entity_type = entity_type #total_inc, sensor, number, switch, 
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.step = step

    def send_entity_autoconfig(self):
        entity_config = self.device.entity_config
        entity_config["name"] = self.device.client_id + " " + self.name
        entity_config["unique_id"] = self.device.client_id + "_" + self.name
        entity_config["icon"] = self.icon
        entity_config["value_template"] = "{{value_json." + self.name + "}}"
        entity_config["state_topic"] = self.device.state_topic

        if self.entity_type == "total_increasing":
            entity_config["device_class"] = "water"
            entity_config["state_class"] = "total_increasing"
            entity_config["state_class"] = self.entity_type
            entity_config["unit_of_measurement"] = self.unit
            self.entity_type = "sensor"

        elif self.entity_type == "number":
            entity_config["command_topic"] = self.device.command_topic
            entity_config["unit_of_measurement"] = self.unit
            entity_config["min"] = self.minimum
            entity_config["max"] = self.maximum
            entity_config["step"] = self.step
            entity_config["command_template"] = "{\"" + self.name + "\": {{ value }}}"

        elif self.entity_type == "switch":
            entity_config["command_topic"] = self.device.command_topic
            entity_config["payload_on"] = "{\"" + self.name + "\": 1}"
            entity_config["payload_off"] = "{\"" + self.name + "\": 0}"
            entity_config["state_on"] = 1
            entity_config["state_off"] = 0

        elif self.entity_type == "sensor":
            entity_config["unit_of_measurement"] = self.unit

        elif self.entity_type == "select":
            entity_config["command_topic"] = self.device.command_topic
            entity_config["command_template"] = "{\"" + self.name + "\": \"{{ value }}\"}"
            entity_config["options"] = self.unit

        else:
            print(messages_getjudo.debug[26])
            return

        autoconf_topic = discovery_topic(self.entity_type, self.device.LOCATION, self.device.NAME + "_" + self.name)
        publish_json(self.device._client, autoconf_topic, entity_config)

    def parse(self, response_data, index, a,b):
        val = response_data["data"][0]["data"][str(index)]["data"]
        if val != "":
            self.value = int.from_bytes(bytes.fromhex(val[a:b]), byteorder='little')

class NotificationEntity():
    def __init__(self, device: JudoDeviceConfig, name, icon, counter=0, value = ""):
        self.device = device
        self.name = name
        self.icon = icon
        self.value = value
        self.counter = counter

    def send_autoconfig(self):
        entity_config = self.device.entity_config
        entity_config["name"] = self.device.client_id + " " + self.name
        entity_config["unique_id"] = self.device.client_id + "_" + self.name
        entity_config["icon"] = self.icon
        entity_config["state_topic"] = self.device.notification_topic
        autoconf_topic = discovery_topic("sensor", self.device.LOCATION, self.device.NAME + "_" + self.name)
        publish_json(self.device._client, autoconf_topic, entity_config)

    def publish(self, message, debuglevel):
        self.value = message
        msg = str(self.value)
        print(f"{time.strftime('%Y-%m-%d %H:%M %Z', time.localtime(time.time()))} - {msg}")
        if self.device.MQTT_DEBUG_LEVEL  >= debuglevel:
            self.device._client.publish(self.device.notification_topic, msg, qos=0, retain=True)

def publish_json(client, topic, message):
    json_message = json.dumps(message)
    result = client.publish(topic, json_message, qos=0, retain=True)

def discovery_topic(entity_type, node_id, object_id, discovery_prefix="homeassistant"):
    # https://www.home-assistant.io/integrations/mqtt/#discovery-topic
    # format: <discovery_prefix>/<component>/[<node_id>/]<object_id>/config
    # only alphanumeric characters, underscores, and hyphens are allowed in node_id and object_id
    node_id = re.sub('[^A-Za-z0-9_-]+', '', node_id.replace(" ", "_"))
    object_id = re.sub('[^A-Za-z0-9_-]+', '', object_id.replace(" ", "_"))
    return f"{discovery_prefix}/{entity_type}/{node_id}/{object_id}/config"