import email 
from imapclient import IMAPClient

import logging
import logging.handlers

import traceback 

moduleLogger = logging.getLogger('gateControl')

IMAP_HOST = 'imap.mymailserver.com'
SMTP_HOST = 'smtp.mymailserver.com'
SMTP_PORT = 465
USERNAME = 'username@mymailserver.com'
PASSWORD = 'myPassword'

# -- GPIO >>>

import os
from time import sleep
import signal
import sys
import RPi.GPIO as GPIO

ERROR_PIN = 20
GATE_CONTROL_PIN = 21 
ACTIVITY_PIN = 26

InstructionValidations = ['secretPassPhrase']
InstructionWalk = ['walk']
InstructionOpenAndLock = ['openandlock']
validSenders = ['authorised.user.1@mymailserver.com', 'authorised.user.2@mymailserver.com', 'authorised.user.3@mymailserver.com']

def setPin(gpioPin, mode):
    GPIO.output(gpioPin, mode)
    return()

def gpioSetup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GATE_CONTROL_PIN, GPIO.OUT)
    setPin(GATE_CONTROL_PIN, False)
    GPIO.setup(ERROR_PIN, GPIO.OUT)
    setPin(ERROR_PIN, False)
    GPIO.setup(ACTIVITY_PIN, GPIO.OUT)
    setPin(ACTIVITY_PIN, False)
    GPIO.setwarnings(False)
    return()

def gpioCleanup():
    GPIO.cleanup()

def triggerGpio(pin, waitDelay):
    try:
        setPin(pin, True)
        sleep(waitDelay)
        setPin(pin, False)
    finally:
        return()

def triggerGate():
    triggerGpio(GATE_CONTROL_PIN, 1)

def triggerErrorIndicator():
    triggerGpio(ERROR_PIN, 1)

def triggerActivityIndicator():
    triggerGpio(ACTIVITY_PIN, 2)

# -- GPIO <<<

# -- SMTP >>>

import smtplib
from datetime import datetime


def sendEmailResponse(recipient):
    try:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.login(USERNAME, PASSWORD)
        emailText = 'From: gate\nTo: %s\nSubject: Gate triggered\n\nCommand processed at %s.' % (recipient, datetime.now().strftime("%H:%M:%S on %Y-%m-%d"))
        server.sendmail(USERNAME, recipient, emailText)
    finally:
        server.close()

# -- SMTP <<<

def isValidSender(sender):
    result = (any(foundString in sender for foundString in validSenders))
    return(result)
   
def isInstructionValid(subject):
    return (any(foundString in subject for foundString in InstructionValidations))

def isNormalTriggerSubject(subject):
    # Activate just once, simulating pressing the remote control button one time. The gate will open and 
    # will automatically close itself after a while.
    result = isInstructionValid(subject.lower())
    return(result)
    
def isWalkOutTriggerSubject(subject):
    # Activate twice, timed so that the gate stops opening leaving a gap of a couple of metres, allowing
    # pedestian access but not vehicular. Also, it will remain open until explicitly closed.
    result = ( isInstructionValid(subject.lower()) and (any(foundString in subject.lower() for foundString in InstructionWalk)) )
    return(result) 
    
def isOpenAndLockTriggerSubject(subject):
    # Activate twice, timed so that the gate stops opening just before the maximum extent is reached - 
    # i.e. just before it's fully open and its own stop mechanism kicks in. In this way, it'll stay open.
    # and not close itself after a while
    result = ( isInstructionValid(subject.lower()) and (any(foundString in subject.lower() for foundString in InstructionOpenAndLock)) )
    return(result) 

def triggerGateForWalkOut():
    moduleLogger.info('Triggering gate for walk out')
    triggerGate()
    sleep(5)
    triggerGate()
    moduleLogger.info('Complete: walk out')
    
def triggerGateForOpenAndLock():
    moduleLogger.info('Triggering gate for open and lock')
    triggerGate()
    sleep(23)
    triggerGate()
    moduleLogger.info('Complete: open and lock')

def main():
    logging.basicConfig(format='%(asctime)s %(message)s')
    moduleLogger.setLevel(logging.INFO)

    continueExecution = True
    try:
        gpioSetup()
        while (continueExecution):
            try:
               with IMAPClient(IMAP_HOST) as client:
                   try:
                       serverResponse = client.login(USERNAME, PASSWORD)
                       while (True):
                           selectFolderResponse = client.select_folder('INBOX', readonly=False)              
                           messages = client.search('UNSEEN')
                           moduleLogger.debug(messages)
                           for uid, message_data in client.fetch(messages, 'RFC822').items():
                               email_message = email.message_from_bytes(message_data[b'RFC822'])
                               emailSender = email_message.get('From')
                               emailSubject = email_message.get('Subject')
                               separator = ' '
                               logContent = ['Processing message:', str(uid), emailSender , emailSubject]
                               moduleLogger.info(separator.join(logContent))
                               try:
                                   if isValidSender(emailSender):
                                       if isWalkOutTriggerSubject(emailSubject):
                                           triggerGateForWalkOut()
                                           sendEmailResponse(emailSender)
                                       elif isOpenAndLockTriggerSubject(emailSubject):
                                           triggerGateForOpenAndLock()
                                           sendEmailResponse(emailSender)
                                       elif isNormalTriggerSubject(emailSubject):
                                           triggerGate()
                                           sendEmailResponse(emailSender)                                      
                               finally:
                                   deleteResponse = client.delete_messages([uid])              
                           triggerActivityIndicator()
                   finally:
                       serverResponse = client.logout()
            except KeyboardInterrupt: # trap a CTRL+C keyboard interrupt
                print('User cancelled through CTRL+C')
                continueExecution = False
            except:
                separator = ' '
                moduleLogger.error(traceback.format_exc())
                triggerErrorIndicator()
                pass
    finally:
        gpioCleanup()
            
if __name__ == '__main__':
    main()



