import boto3
import automationhat
from twilio.rest import Client
import json
import time
from phue import Bridge
import configparser
import argparse

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

        #Read key conf variables
        self.text_queue_url = settings.get('text_queue_url')
        self.callback_queue_url = settings.get('text_queue_url')
        self.account_sid = settings.get('account_sid')
        self.auth_token = settings.get('auth_token')
        self.whitelistednumbers = settings.get('whitelist')
        try:
            hue_bridge_ip = settings.get('hue_bridge_ip')
            hue_bridge_username = settings.get('hue_bridge_username')
            hue_light_name = settings.get('hue_light_name')
            self.hue_enabled = True
        except NoOptionError:
            print('No Hue bridge config - lights will not work.')
            self.hue_enabled = False

        #Set up queues
        self.queue_client = boto3.client('sqs')
        self.twilio_client = Client(self.account_sid, self.auth_token)
        if self.hue_enabled==True:
            try:
                hue_bridge = Bridge(hue_bridge_ip,hue_bridge_username)
                hue_bridge.connect()
                lights = hue_bridge.get_light_objects('name')
                self.light = lights[hue_light_name]
            except:
                print('Error initializing Hue bridge - lights will not work')
                self.hue_enabled = False
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
        message_body = message['Body']
        if message_source in self.whitelistednumbers:
            print('message source validated')
            self.send_sms(message_source,'Phone number whitelisted, opening door')
            return 1
        else:
            print('unknown message source')
            self.send_sms('+16172296072',message_source+': '+message_body)
            self.send_sms(message_source,'Phone number not known')
            return -1

    def lights_on(self):
        hue = self.light.hue
        bri = self.light.brightness
        state = self.light.on
        sat = self.light.saturation
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
        self.light.hue = 0
        cycle_count = 0 
        while cycle_count <= 3:
            if sepf.light.hue >= 65000:
                self.light.hue = 0
                cycle_count += 1
            self.light.hue += 500


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
                    if self.validate_sms(json.loads(message['Body'])) == 1:
                        self.open_door()
                        if self.hue_enabled==True:
                            try:
                                self.lights_on()
                            except:
                                self.hue_enabled==False
            else:
                print('Queue Empty')

if __name__=="__main__":
    doorbell().poller()
