from imutils.video import VideoStream
from pyzbar import pyzbar
import argparse
import datetime
import imutils
import time
import cv2

# Setea la salida por default a un archivo csv (historial)
ap = argparse.ArgumentParser()
ap.add_argument("-o", "--output", type=str, default="decodedQRs.csv",
	help="Output file for decoded codes.")
args = vars(ap.parse_args())

# Inicializa el stream de video
print("[INFO] starting video stream...")
vs = VideoStream(src=0).start()
# Delay para la correcta inicializacion de la camara
time.sleep(2.0)

# Archivo de salida
csv = open(args["output"], "w")
found = set()

# Loopea sobre el stream de video
while True:
	# Captura el frame y lo redimensiona
	frame = vs.read()
	frame = imutils.resize(frame, width=400)

	# Le pasa el frame a zbar para su analisis
	barcodes = pyzbar.decode(frame)

	# Por si existiera mas de un qr en el frame
	for barcode in barcodes:
		# Resalta el area del qr detectado
		(x, y, w, h) = barcode.rect
		cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

		# Decodifica el qr a string
		barcodeData = barcode.data.decode("utf-8")

		# Imprime el texto decodificado
		text = "{}".format(barcodeData)
		cv2.putText(frame, text, (x, y - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

		# Filtro qr ya leidos
		if barcodeData not in found:
			csv.write("{},{}\n".format(datetime.datetime.now(),
				barcodeData))
			# Flushea el buffer
			csv.flush()
			# Actualiza el set
			found.add(barcodeData)
			print("[DEBUG] found a new code: {}".format(barcodeData))

	# Manda el frame a la pantalla (debug)
	cv2.imshow("QR Scanner", frame)
	
	# Tecla de escape
	key = cv2.waitKey(1) & 0xFF
	if key == ord("q"):
		break

# Cierra el decoder
print("[INFO] stopping decoder...")
csv.close()
cv2.destroyAllWindows()
vs.stop()