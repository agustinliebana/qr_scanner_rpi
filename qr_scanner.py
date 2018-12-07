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
import time

# Mocks de respuestas del webserver para validaciones positivas y negativas
okUrl = 'http://www.json-generator.com/api/json/get/bUBTBcgqUO'
notOkUrl = 'http://www.json-generator.com/api/json/get/bUQJTmEgpu'

# Constantes de configuración
SERVER = '192.168.100.2:8080/decoder'
AUTH_TOKEN = 'b67330ebbcdfa68729893f7e1f75840c'
USER_ID      = 27
GREEN_LED    = 18
RED_LED      = 12
YELLOW_LED   = 11
STAND_BY_LED = 32

# Configura los pines correspondientes a los LEDs como salidas y su valor inicial
GPIO.setmode(GPIO.BCM)
GPIO.setup(GREEN_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(RED_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(YELLOW_LED, GPIO.OUT, initial=GPIO.LOW)
GPIO.setup(STAND_BY_LED, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setwarnings(False)


# Método para obtener información del webserver (actualmente sin uso aunque fue pensado para generar un SNAPSHOT de la db para ser útil en caso de falta de conectividad GSM/LTE)
def getData(path):
    print('[DEBUG] Trying to fech data from {}'.format(path))
    requestData = requests.get(path)
    print('[DEBUG] Obtenined this {}'.format(requestData.json()))
    return requestData.json()

# Valida el ticket leido por QR con el webserver
def postData(ticket, journey):
    url = SERVER + '/ticket/{0}/journey/{1}/check'.format(ticket, journey)
    print('[DEBUG] Trying to hit {} to validate the ticket'.format(url))
    payload = {}
    headers = {
        'passengerId': USER_ID,
        'authToken': AUTH_TOKEN
    }
    requestData = requests.post(url, data=json.dumps(payload), headers=headers)
    print('[DEBUG] Server response: {}'.format(requestData.status_code))
    return requestData.json()

# Parsea la respuesta de la validación del servidor y devuelve el estado de la misma
def parseValidation(raw):
    objectArray = json.loads(raw)
    status = ''
    for o in objectArray:
        print('[INFO] Ticked ID: {}'.format(o.get('ticketId')))
        print('[INFO] Journey ID: {}'.format(o.get('journeyId')))
        status += o.get('status')
        print('[INFO] Status: {}'.format(status))
    return status

# Parsea una url, utilizado en una versión previa aunque se decidió dejarlo hasta confirmar su remoción.
def parseUrl(raw):
    objectArray = json.loads(raw)
    url = ''
    for o in objectArray:
        url += o.get('url')
    return url


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
csv = open(args['output'], 'w')
# Cache de QRs leidos
found = set()

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
            print('[DEBUG] YELLOW led ON')
            GPIO.output(YELLOW_LED, GPIO.HIGH)
            
            csv.write('{},{}\n'.format(datetime.datetime.now(), barcodeData))
            # Flushea el buffer
            csv.flush()
            # Actualiza el set
            found.add(barcodeData)

            print('[DEBUG] found a new code: {}'.format(barcodeData))

            url = parseUrl(barcodeData)

            data = getData(url)

            status = parseValidation(json.dumps(data))

            if status == 'OK':
                print('[INFO] Ticket approved.')
                print('[DEBUG] GREEN led ON')
                GPIO.output(GREEN_LED, GPIO.HIGH)
            else:
                print('[INFO] Invalid ticket for this journey.')
                print('[DEBUG] RED led ON')
                GPIO.output(RED_LED, GPIO.HIGH)

            time.sleep(3)

            print('[DEBUG] Leds OFF')
            GPIO.output(GREEN_LED, GPIO.LOW)
            GPIO.output(RED_LED, GPIO.LOW)
            GPIO.output(YELLOW_LED, GPIO.LOW)
        else:
            print('[INFO] Ticket was alredy used.')
            print('[DEBUG] RED led ON')
            GPIO.output(RED_LED, GPIO.HIGH)
            time.sleep(3)
            print('[DEBUG] RED led OFF')
            GPIO.output(RED_LED, GPIO.LOW

    # Manda el frame a la pantalla (debug)
    cv2.imshow('QR Scanner', frame)

    # Tecla de escape
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

# Cierra el decoder
print('[INFO] Shutting down...')
csv.close()
cv2.destroyAllWindows()
vs.stop()
