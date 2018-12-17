from imutils.video import VideoStream
from pyzbar import pyzbar
import argparse
import datetime
import imutils
import time
import cv2
import requests
import json
import RPi.GPIO as GPIO

# Constantes de configuración
SERVER_URL = 'http://181.231.69.210:9290/api/v1'
AUTH_TOKEN = 'terminal'
USER_ID      = '2'
GREEN_LED    = 20
RED_LED      = 12
YELLOW_LED   = 21
STAND_BY_LED = 18
INTERVAL     = 4

# Configura los pines correspondientes a los LEDs como salidas y su valor inicial
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(GREEN_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RED_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(YELLOW_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(STAND_BY_LED, GPIO.OUT, initial=GPIO.HIGH)

def logAndUpdate(data):
    csv.write('{} - {}\n'.format(datetime.datetime.now(), data))
    # Flushea el buffer
    csv.flush()
    # Actualiza el set
    found.add(data)

# Método para obtener información del webserver (actualmente sin uso aunque fue pensado para generar un SNAPSHOT de la db para ser útil en caso de falta de conectividad GSM/LTE)
def getData(path):
    print('[DEBUG] Trying to fech data from {}'.format(path))
    requestData = requests.get(path)
    print('[DEBUG] Obtenined this {}'.format(requestData.json()))
    return requestData.json()

# Valida el ticket leido por QR con el webserver
def postData(ticket, journey):
    url = SERVER_URL + '/ticket/{0}/journey/{1}/check'.format(ticket, journey)
    print('[DEBUG] Trying to hit {} to validate the ticket'.format(url))
    payload = {}
    headers = {
        'passengerId': USER_ID,
        'authToken': AUTH_TOKEN
    }
    
    try:
        requestData = requests.post(url, data=json.dumps(payload), headers=headers, timeout=5)
        statusCode = requestData.status_code
        print('[DEBUG] Server response: {}'.format(statusCode))
        if statusCode == 200:
            return requestData.json()
    except:
        print('[WARN] Server timeout! Aborting...')
        return None
        
        
    

def jsonIzer(jsonString):
    return '['+jsonString+']'

def ledColor(x):
    return {
        20 : 'GREEN',
        12 : 'RED',
        21 : 'YELLOW',
    }[x]

def ledOn(led):
    print('[DEBUG] {} led ON'.format(ledColor(led)))
    GPIO.output(led, GPIO.HIGH)
    
def ledOff(led):
    print('[DEBUG] {} led OFF'.format(ledColor(led)))
    GPIO.output(led, GPIO.LOW)

# Parsea la respuesta de la validación del servidor y devuelve el estado de la misma
def parseValidation(raw):
    jArray = jsonIzer(raw)
    objectArray = json.loads(jArray)

    try:
        for o in objectArray:
            print('[INFO] Server response:')
            print('******************************************')
            print('[INFO] Ticket ID: {}'.format(o.get('ticketId')))
            print('[INFO] Journey ID: {}'.format(o.get('journeyId')))
            status = o.get('status')
            print('[INFO] Status: {}'.format(status))
            print('******************************************')
        return status
    except:
        print('[DEBUG] Cannot validate this QR.')
        return None

# Parsea una url, utilizado en una versión previa aunque se decidió dejarlo hasta confirmar su remoción.
def parseUrl(raw):
    objectArray = json.loads(raw)
    url = ''
    for o in objectArray:
        url += o.get('url')
    return url

def parseQr(raw):
    jArray = jsonIzer(raw)
    print('[DEBUG] JSONnizer result: {}'.format(jArray))
    try:
        objectArray = json.loads(jArray)
        return objectArray[0].get('ticketId'), objectArray[0].get('journeyId')
    except:
        print('[DEBUG] Cannot parse this QR.')
        return None, None


def shutdown():
    # Cierra el decoder
    print('[INFO] Shutting down...')
    csv.write('{} - System Shut Down!\n'.format(datetime.datetime.now()))
    csv.close()
    cv2.destroyAllWindows()
    vs.stop()


# Setea la salida por default a un archivo csv (historial)
ap = argparse.ArgumentParser()
ap.add_argument('-o', '--output', type=str, default='decodedQRs.csv',
                help='Output file for decoded codes.')
args = vars(ap.parse_args())

# Inicializa el stream de video
print('[INFO] Starting video stream...')
vs = VideoStream(src=0).start()
# Delay para la correcta inicialización de la cámara
time.sleep(2.0)

# Archivo de salida
csv = open(args['output'], 'a')
# Cache de QRs leidos
found = set()

csv.write('{} - System Up!\n'.format(datetime.datetime.now()))
print('[INFO] Starting decoder...')

# Loopea sobre el stream de video
while True:
    # Captura el frame y lo redimensiona
    frame = vs.read()
    frame = imutils.resize(frame, width=400)

    # Le pasa el frame a zbar para su análisis
    barcodes = pyzbar.decode(frame)

    # Por si existiera mas de un QR en el frame
    for barcode in barcodes:
        # Resalta el area del qr detectado
        (x, y, w, h) = barcode.rect
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # Decodifica el qr a string
        barcodeData = barcode.data.decode('utf-8')

        # Imprime el texto decodificado
        text = "{}".format(barcodeData)
        cv2.putText(frame, text, (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Filtro QRs ya leidos
        if barcodeData not in found:
            #print('[DEBUG] YELLOW led ON')
            #GPIO.output(YELLOW_LED, GPIO.HIGH)
            ledOn(YELLOW_LED)
            
            logAndUpdate(barcodeData)

            print('[DEBUG] found a new code: {}'.format(barcodeData))
            
            ticketId, journeyId = parseQr(barcodeData)
            
            data = None
            
            if ((ticketId != None) or (journeyId != None)):
                data = postData(ticketId, journeyId)
            
            if data is not None:
                print('[DEBUG] JSON response: {}'.format(data))

                status = parseValidation(json.dumps(data))

                if status == 'OK':
                    print('[INFO] Ticket approved.')
                    ledOn(GREEN_LED)
                else:
                    print('[WARN] Invalid ticket for this journey.')
                    ledOn(RED_LED)
                    
                time.sleep(INTERVAL/2)    
                ledOff(YELLOW_LED)
                time.sleep(INTERVAL)

                print('[DEBUG] Leds OFF')
                ledOff(RED_LED)
                ledOff(GREEN_LED)
        else:
            ledOn(RED_LED)
            
            if data is not None:
                print('[INFO] Ticket was alredy used.')
                
            time.sleep(INTERVAL)
            ledOff(RED_LED)

    # Manda el frame a la pantalla (debug)
    cv2.imshow('QR Scanner', frame)

    # Tecla de escape
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

shutdown()