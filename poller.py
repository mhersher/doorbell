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
            self.hue_enabled = True
        except NoOptionError:
            print('No Hue bridge config - lights will not work.')
            self.hue_enabled = False

        #Set up queues
        queue_client = boto3.client('sqs')
        twilio_client = Client(account_sid, auth_token)
        if self.hue_enabled==True:
            try:
                self.hue_bridge = Bridge(hue_bridge_ip)
            except PhueException:
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
        message = twilio_client.messages.create(body=content,to=destination,from_='+14159081771')
        print(message.sid)

    def validate_sms(self,message):
        message_source = message['From']
        message_sid = message['SmsMessageSid']
        message_body = message['Body']
        if message_source in self.whitelistednumbers:
            print('message source validated')
            send_sms(message_source,'Phone number whitelisted, opening door')
            return 1
        else:
            print('unknown message source')
            send_sms('+16172296072',message_source+': '+message_body)
            send_sms(message_source,'Phone number not known')
            return -1

    def lights_on(self):
        hue_bridge.connect()
        hue_bridge.set_group(1,'on',True)
        hue_bridge.set_group(1,'bri',254)

    def open_door(self):
        if debug==True:
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
            messages = queue_client.receive_message(QueueUrl=text_queue_url)
            print('Queue response received')
            if 'Messages' in messages:
                for message in messages['Messages']:
                    queue_client.delete_message(QueueUrl=text_queue_url,ReceiptHandle=message['ReceiptHandle'])
                    if validate_sms(json.loads(message['Body']))  == 1:
                        self.open_door()
                        self.lights_on()
            else:
                print('Queue Empty')

if __name__=="__main__":
    doorbell().poller()
