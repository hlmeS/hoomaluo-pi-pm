#!/usr/bin/env python3

"""

Title: Hoomaluo - Power Monitor
Project: Power Monitoring system
Author: Hoomaluo Labs
Version: 1.0
Date: 09-25-2018

Overview:
* Communicate with a server over MQTT:
    - report temperature and energy
        * store locally if disconnected
        * report local data once back online
    - receive control inputs
* Communicate with STM32 uController over RS232:
    -  send status, temp setpoint, and IR command
    -  receive power (ac and dc) and temperature as json object
* Read GPIO buttons for controls
* Different modes are:
    - 4-wye : 4-wire wye with 3 cts and 3 voltages
    - 4-delta : 4-wire delta with 3 cts and 3 voltages
    - 3-1ph : 3-wire 1 phase with 2 cts and 1 voltage
    - m-1ph : multiple 1phase circuits with 1ct and voltage per circuit

Packages:
* paho-mqtt ; for mqtt communication: https://pypi.python.org/pypi/paho-mqtt/1.1
* pandas
* numpy
* threading


"""
from time import sleep,time
import datetime
import paho.mqtt.client as mqtt
import json
import threading
import os
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from gpiozero import Button
import serial
import configparser

#global debug
#debug = True

def c2f(c):
    return (9/5)*c+32

def f2c(c):
    return (5/9)*(F-32)

class Container:
    def __init__(self, serialConnection, mode, Controller, kwhFilename="kwh-meter.txt"):
        """ initialize variables """


        self.ts = int(time())
        self.mode = mode
        if self.mode is not 0:
            self.payload = ""
        self.awatts = []
        self.bwatts = []
        self.cwatts = []
        self.kwh = 0
        self.ace_accum = 0
        self.dce_accum = 0
        self.ser = serialConnection
        self.kwhFile = kwhFilename
        self.controller = Controller


    def read_kwhMeter(self):
        "read and return the current kwh reading"
        try:
            with open(self.kwhFile, 'r') as file:
                reading = file.readline()
                file.close()
                return float(reading.strip('\n'))
        except:
            return 0

    def write_kwhMeter(self, reading):
        "overwrite existing file with the new reading"
        with open(self.kwhFile, 'w+') as file :
            file.write('%.6f' % reading + "\n")
            file.close()

    def sendBytesToSTM(self, byteArray):
        if self.ser.is_open:
            if debug: print("Serial is open. Sending: ", byteArray)
            self.ser.write(byteArray)
        else:
            try:
                self.ser.open()
                if debug: print("Serial is open. Sending: ", byteArray)
                self.ser.write(byteArray)
            except:
                if debug: print("Cannot open port.")
                """ TODO: need some routine to try again if failed """

    def readSTM(self, ser):
        "read temp and energy from the STM ... comes in as a json object I think"
        while True:
            if ser.is_open:
                self.processReading(ser.read_until(), int(time())) # adjust character based on code
            else:
                try:
                    ser.open()
                    self.processReading(ser.read_until('\n'), int(time())) # adjust character based on code
                except:
                    if debug: print("Cannot read from port .")
                """ TODO: need some routine to try again if failed """

    def processReading(self, reading, ts, serialDebug=False):
        """ update energy accumulators based on power readings and time interval
        Sample:
        readings = u'{"temp":70.00,"temp2":70.00,"awatt":-0.01,"ava":-0.01,"apf":1.00,"avrms":73735.22,"airms":18318.55,"awatt2":-0.01,"ava2":-0.01,"apf2":1.00,"avrms2":18318.55,"bwatt":-0.01,"bva":-0.01,"bpf":1.00,"bvrms":73735.22,"birms":18318.55,"bwatt2":-0.01,"bva2":-0.01,"bpf2":1.00,"birms2":18318.55,"cwatt":-0.01,"cva":-0.01,"cpf":1.00,"cvrms":73735.22,"cirms":18318.55,"cwatt2":-0.01,"cva2":-0.01,"cpf2":1.00,"cirms2":18318.55,"dcp":0.00,"dcv":0.01,"dci":0.00,"dcp2":0.00,"dcv2":0.06,"dci2":0.01}'
        """
        # convert string to json
        if serialDebug:
            print(reading)
            print(type(reading))

        if isinstance(type(reading), str):
            try:
                a = json.loads(reading)
                self.processJSONformat(a)
            except:
                if serialDebug:
                    print("cannot")
                    print("could not process string")
        else:
            try:
                b = json.loads(reading.decode("utf-8").replace('\r', '').replace('\n', ''))
                self.processJSONformat(ts, b)
            except:
                if serialDebug:
                    print("could not process byte string")
                    print ("no can")


    def processJSONformat(self, ts, a):
        # get time interval
        timedelta = ts - self.ts
        self.ts = ts

        # calculate energies
        """
            - 4-wye : 4-wire wye with 3 cts and 3 voltages
            - 4-delta : 4-wire delta with 3 cts and 3 voltages
            - 3-1ph : 3-wire 1 phase with 2 cts and 1 voltage
            - m-1ph : multiple 1phase circuits with 1ct and voltage per circuit
        """

        #self.kwh += timedelta * (a['awatt'] + a['bwatt'] + a['cwatt']) / (3600.0 * 1000)     # kwatt-hour
        self.awatts.append(a['awatt'])
        self.bwatts.append(a['bwatt'])
        self.cwatts.append(a['cwatt'])
        if a['awatt'] > 0 and a['bwatt'] > 0 :
            self.ace_accum += timedelta * (a['awatt'] + a['bwatt'] + a['cwatt']) / (3600.0 * 1000)    # watt-hour
        #self.dce_accum =                     # watt-hour
        self.irms.append(a['airms'])
        self.vrms.append(a['avrms'])
        self.watts.append(a['awatt'] + a['bwatt'] + a['cwatt'])


        if debug:
            print("kwh: ", self.kwh, "a: ", a['awatt'], "b:", a['bwatt'], "c:", a['cwatt'])


    def resetEnergyAccumulators(self):
        self.awatts = []
        self.bwatts = []
        self.cwatts = []
        if self.ace_accum > 0:
            self.kwh = self.read_kwhMeter() + self.ace_accum
            self.write_kwhMeter(self.kwh)
        self.sendStringToSTM('%.5f' % self.kwh + "?kwh")
        self.ace_accum = 0
        #self.dce_accum = 0             # no dc component
        self.watts = []
        self.irms = []
        self.vrms = []


class Radio:
    def __init__(self, devId, custId, Controller, localFilename):

        self.devId = devId
        self.custId = custId

        self.controller = Controller
        # subscriptions
        self.subSettings = "maluo_1/pm/set/"+custId+"/"+devId+"/info"

        # publishing
        self.pubEnergy = "maluo_1/pm/metering/energy/"+custId+"/"+devId

        self.storeLocalEnergy = False
        self.midEnergy = 0
        self.lastEnergyPayload = ""

        # MQTT client
        self.client = mqtt.Client(devId)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish


        # Need to fix this to attempt reconnect
        try:
            self.client.connect("post.redlab-iot.net", 55100, 60)
            if debug: print("connection established")
        except:
            if debug: print("connection failed")

        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        """ Callback function when client connects """
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        sleep(5)                # quick delay
        self.client.subscribe(self.subSettings)

    def on_publish(self, client, userdata, mid):
        """ Callback function that's called on successful delivery (need qos 1 or 2 for this to make sense) """
        if debug: print("on_publish ... \nuserdata: ", userdata, "\nmid: ", mid)

        elif mid == self.midEnergy:
            self.storeLocalEnergy = False

    def on_message(self, client, userdata, msg):
        """ Callback function when client receives message """

        data = json.loads(msg.payload.decode("utf-8"))
        if debug: print("topic: ", msg.topic, " payload:", data)
        #print "Received: ", data
        if msg.topic == self.subSettings :
            self.controller.energy_interval = int(data['energy-res'])
            self.controller.updateIntervals()
        else:
            pass

    def sendEnergy(self, payload):
        res, self.midEnergy = self.client.publish(self.pubEnergy, payload, qos=1, retain=False)
        if debug: print("Sent: ", payload , "on", self.pubEnergy, "mid: ", self.midEnergy)

        filename = self.pubEnergy.replace("/", "-") + ".txt"
        if self.storeEnergyLocal:
            open(filename, 'a+').writelines(self.lastEnergyPayload+"\n")
        self.storeLocalEnergy = True
        self.lastEnergyPayload = payload

    def sendLocalEnergy(self):
        if self.connectionStatus:
            filename = self.pubEnergy.replace("/", "-") + ".txt"
            try:
                lines = open(filename, 'r').readlines()
                for i, line in enumerate(lines[:]):
                    if '{' in line.strip("\n"):
                        self.sendEnergy(line.strip("\n"))
                    del lines[i]
                    sleep(15)

                open(filename, 'w+').writelines(lines)

            except:
                pass


class Monitor:
    def __init__(self):

        config = configparser.ConfigParser()
        config.read('config.ini')

        # DEFAULTS
        self.radio = config["DEFAULT"]["radio"]
        self.tempres = int(config["DEFAULT"]["tempres"])
        self.logMode = int(config["DEFAULT"]["logMode"])
        self.serPort = config["DEFAULT"]["serPort"]
        self.ser = serial.Serial(self.serPort)  # open serial port
        global debug
        debug = eval(config["DEFAULT"]["debug"])
        print(debug)
        # [DEVICE]
        self.devId = config["DEVICE"]["devId"]
        self.custId = config["DEVICE"]["custId"]
        devType = config["DEVICE"]["devType"]

        self.displayCode = 0
        self.loggingState = 0
        self.logCount = 0

        #self.localFile = str(int(time())) + "_log.txt"
        self.myContainer = Container(self.ser, self.logMode, self)

        if self.radio is "yes":
            self.myRadio = Radio(self.devId, self.custId, self)

        self.scheduler = BackgroundScheduler({'apscheduler.timezone': 'HST'})


        if self.loggingState == 1:
            self.addLoggerJob()

        if self.radio is "yes":
            self.addLocalEnergyFileJob()

        self.sendToSTM(str(self.loggingState) + "?record")

        self.addJobs()
        self.scheduler.start()

    def addLoggerJob(self):
        self.energyLogger = self.scheduler.add_job(self.logEnergy,
                            'cron',
                            minute='*/'+str(self.tempres),  args=[str(int(time())) + "_log.txt"])

    def addLocalEnergyFileJob(self):
        self.sendLocalEnergyFile = self.scheduler.add_job(self.myRadio.sendLocalEnergy,
                                'cron',
                                hour=w)

    def addJobs(self):
        if debug: print("added jobs")


        #self.simSwitchButton = self.scheduler.add_job(self.buttonSwitchPushed,
        #                        'interval',
        #                        minutes=1)
        #self.simStartButton = self.scheduler.add_job(self.buttonStartPushed,
        #                        'interval',
        #                        minutes = 2)
        # add daily check for local storage
        # add 15 min update for screen?


    def updateIntervals(self):
        """ update the intervals for sending temperature and energy """
        for job in self.scheduler.get_jobs():
            job.remove()
        self.addJobs()

    def updateLoggingSchedule(self):
        if self.loggingState is 0:
            self.energyLogger.remove()
            self.logCount = 0
        else:
            self.addLoggerJob() #wor()k around for now

    def logEnergy(self, filename="log.txt"):

        """ send availability to self.pubEnergy """

        if len(self.myContainer.awatts) is not 0:
            awatts = sum(self.myContainer.awatts) / len(self.myContainer.awatts)
            bwatts = sum(self.myContainer.bwatts) / len(self.myContainer.bwatts)
            cwatts = sum(self.myContainer.cwatts) / len(self.myContainer.cwatts)
        else:
            awatts = bwatts = cwatts = 0

        self.myContainer.resetEnergyAccumulators()
        ts = str(int(time()))

        if self.radio is "yes":
            payload = ('{"ts": '+ str(int(time())) +  ', "kwh": ' +  '%.5f' % self.controller.myContainer.read_kwhMeter()
                        + ', "ace": ' + '%.5f' % self.controller.myContainer.ace_accum
                        + ', "dce": ' + '%.5f' % self.controller.myContainer.dce_accum
                        + ', "data": { "watt": ' + '%.5f' % watts + ', "vrms": '+ '%.5f' % vrms
                        + ', "irms": '+ '%.5f' % irms  + ' }}' )

            self.myRadio.sendEnergy(payload)

        line = ts + ", " + str(awatts) + ", " + str(bwatts) + ", " + str(cwatts) + "\n"

        try:
            open(filename, 'a+').writelines(line)
            if debug: print("logging: ", line)
        except:
            pass

    def buttonStartPushed(self):
        if debug: print("record button pushed!")
        self.loggingState = abs(self.loggingState - 1)
        self.updateLoggingSchedule()
        self.sendToSTM(str(self.loggingState) + "?record")


    def buttonSwitchPushed(self):
        if debug: print("switch button pushed!")
        self.displayCode += 1
        if self.displayCode is 4:
            self.displayCode = 0
        self.sendToSTM(str(self.displayCode) + "?" + str(self.logCount) + "?display")

    def sendToSTM(self, message) :
        self.myContainer.sendBytesToSTM(message.encode("utf-8"))

def main():
    myMonitor = Monitor()
    onButton = Button(9)
    switchButton = Button(5)
    onButton.when_pressed = myMonitor.buttonStartPushed
    switchButton.when_pressed = myMonitor.buttonSwitchPushed

    # serial read is a seperate thread
    ser_thread = threading.Thread(target=myMonitor.myContainer.readSTM, args = [myMonitor.ser])
    print("start serial read thread")
    ser_thread.start()


    try:
        while True:
            sleep(10)

    except (KeyboardInterrupt, SystemExit):
        # Not strictly necessary if daemonic mode is enabled but should be done if possible
        myMonitor.scheduler.shutdown()

if __name__ == "__main__":
    main()
