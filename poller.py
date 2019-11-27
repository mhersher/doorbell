import boto3
import automationhat
from twilio.rest import Client
import json
import time
from phue import Bridge
import configparser
import argparse
import re
import html
import requests
import phonenumbers
import csv
import pychromecast

class doorbell(object):
    def __init__(self):
        self.read_arguments()
        print('reading configuration from file...')
        config = configparser.ConfigParser()
        config.read(self.config_file)
        for key in config['DEFAULT']:
            print(key+':', config['DEFAULT'].get(key))
        settings = config['DEFAULT']
        print('...configuration read successfully')
        logfile = open(settings.get('log_folder')+'doorbell.log', 'a',1)
        if self.debug == True:
            print('debug mode enabled')
        else:
            sys.stdout = logfile
            sys.stderr = logfile

        #Set Up Amazon and Twilio queues
        self.text_queue_url = settings.get('text_queue_url')
        self.callback_queue_url = settings.get('text_queue_url')
        self.account_sid = settings.get('account_sid')
        self.auth_token = settings.get('auth_token')
        self.queue_client = boto3.client('sqs')
        self.twilio_client = Client(self.account_sid, self.auth_token)

        #Set Up Authorized Users & Access Control
        try:
            self.access_code = settings.get('access_code')
        except NoOptionError:
            print('No access code set')
            self.access_code = False
        if settings.get('auth_whitelist')==True:
            self.auth_whitelist=True
            self.auth_users_csv = settings.get('auth_users_csv')
            self.auth_users = {}
            self.default_sound_url = settings.get('default_sound')
            self.update_auth_users()
        else:
            self.auth_whitelist=False

        #Set Up Hue Lights
        if settings.get('hue_lights') == True:
            try:
                hue_bridge_ip = settings.get('hue_bridge_ip')
                hue_bridge_username = settings.get('hue_bridge_username')
                hue_light_name = settings.get('hue_light_name')
                self.hue_enabled = True
                try:
                    hue_bridge = Bridge(hue_bridge_ip,hue_bridge_username)
                    hue_bridge.connect()
                    lights = hue_bridge.get_light_objects('name')
                    self.light = lights[hue_light_name]
                except:
                    print('Error initializing Hue bridge - lights will not work')
                    self.hue_enabled = False
            except NoOptionError:
                print('No Hue bridge config - lights will not work.')
                self.hue_enabled = False
        else:
            self.hue_enabled = False

        print('Setup Completed')

        #Set Up Chromecast
        if settings.get('chromecast_sounds') == True:
            chromecasts = pychromecast.get_chromecasts()
            self.cast = next(cc for cc in chromecasts if cc.device.friendly_name == self.chromecast_name)


    def update_auth_users(self):
        users_csv = requests.get(csv_url).text.split('\n')
        dictparser = csv.DictReader(phone_csv,delimiter=',')
        for row in dictparser:
            try:
                parsed_phone = phonenumbers.format_number(phonenumbers.parse(row['Phone'], 'US'), phonenumbers.PhoneNumberFormat.E164)
                self.auth_users[parsed_phone]={'Name':row['Name'],'Sound':row['Sound']}
            except phonenumbers.phonenumberutil.NumberParseException:
                print('Invalid Phone Number for',row['Name'])

    def read_arguments(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-c","--config_file",
            dest='config_file',
            help='config file',
            required=True
            )
        parser.add_argument(
            "-d", "--debug",
            default=False,
            action='store_true',
            help='run in debug mode'
            )
        args = parser.parse_args()
        if args.debug:
            self.debug = True
        else:
            self.debug = False
        self.config_file = args.config_file

    def send_sms(self,destination,content):
        message = self.twilio_client.messages.create(body=content,to=destination,from_='+14159081771')
        print(message.sid)

    def validate_sms(self,message):
        message_source = message['From']
        message_sid = message['SmsMessageSid']
        message_body = message['Body'].lower()
        self.update_auth_users()

        #Validate whether the message will unlock the door.
        if self.auth_whitelist is not False and message_source in self.auth_numbers.keys():
            print('message source validated')
            self.send_sms(message_source,'Phone number whitelisted, opening door')
            sound = auth_numbers[message_source]['Sound']
            lights = True
            validation_status = 1
        elif self.access_code is not False and message_body==self.access_code:
            print('valid access code')
            sound = self.default_sound_url
            lights = True
            self.send_sms(message_source,'Access code confirmed, opening door')
            validation_status = 2
        else:
            print('unknown message source')
            self.send_sms('+16172296072',message_source+': '+message_body)
            self.send_sms(message_source,'Invalid access code.  Please try again.')
            validation_status = -1
            lights = False
            sound = False

        #If the message unlocks the door, check to see if there's another action.
        if 'quiet' in message_body:
            lights = False
            sound = False

        return validation_status, lights, sound

    def lights_on(self):
        print('turning lights on')
        if self.debug == True:
            self.light.on = True
            self.light.brightness = 254
            time.sleep(1)
            self.light.on = False
            time.sleep(1)
            self.light.on = True
            time.sleep(1)
            self.light.on = False
            return
        self.light.on = True
        self.brightness = 254

    def rainbow_lights(self):
        print('Doing rainbow lights')
        previous_state = self.light.on
        previous_hue = self.light.hue
        previous_sat = self.light.saturation
        previous_brightness = self.light.brightness
        self.light.on = True
        self.light.brightness = 254
        self.light.hue = 0
        self.light.saturation = 254
        cycle_count = 0
        while cycle_count == 0:
            if self.light.hue >= 63000:
                cycle_count += 1
                self.light.hue = 0
                print(cycle_count)
            self.light.hue += 2000
        self.light.hue = previous_hue
        self.light.brightness = previous_brightness
        self.light.saturation = previous_sat
        self.light.on = previous_state

    def play_message(self,url):
        print('playing sound from',url)
        mc = self.cast.media_controller
        mc.play_media(url)

    def open_door(self):
        if self.debug==True:
            print('debug mode active: would open door now')
        else:
            print('opening door')
            automationhat.relay.one.on()
            time.sleep(2)
            automationhat.relay.one.off()
            print('door locked again')
        return

    def poller(self):
        while True:
            print('Polling for messages')
            messages = self.queue_client.receive_message(QueueUrl=self.text_queue_url)
            print('Queue response received')
            if 'Messages' in messages:
                for message in messages['Messages']:
                    self.queue_client.delete_message(QueueUrl=self.text_queue_url,ReceiptHandle=message['ReceiptHandle'])
                    message_validation, lights, sound = self.validate_sms(json.loads(message['Body']))
                    if message_validation > 0:
                        self.open_door()
                        if lights = True and self.hue_enabled==True:
                            try:
                                self.rainbow_lights()
                            except:
                                self.hue_enabled==False
                                print('Disabling hue')
                        if action != False:
                            self.play_message(action)
            else:
                print('Queue Empty')

if __name__=="__main__":
    doorbell().poller()
