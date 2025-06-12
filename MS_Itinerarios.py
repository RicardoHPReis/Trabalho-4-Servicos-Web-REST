from flask import Flask, request, jsonify
import shared.utils as utils
import threading
import unidecode
import pika
import json

app = Flask(__name__)

itinerarios = utils.carregar_dados("./json/itinerarios.json")

# Conexão com RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

def callback(ch, method, properties, body):
    msg = json.loads(body)
    destino = unidecode.unidecode(msg["destino"].lower().strip())
    if method.routing_key == "reserva-criada":
        if destino in itinerarios:
            itinerarios[destino]["cabines_disponiveis"] -= msg["cabines"]
            utils.salvar_dados("./json/itinerarios.json", itinerarios)
    elif method.routing_key == "reserva-cancelada":
        if destino in itinerarios:
            itinerarios[destino]["cabines_disponiveis"] += msg["cabines"]
            utils.salvar_dados("./json/itinerarios.json", itinerarios)

def start_consumer():
    channel.queue_declare(queue="reserva-criada", durable=True)
    channel.queue_declare(queue="reserva-cancelada", durable=True)

    channel.basic_consume("reserva-criada", callback, auto_ack=True)
    channel.basic_consume("reserva-cancelada", callback, auto_ack=True)

    channel.start_consuming()


threading.Thread(target=start_consumer, daemon=True).start()


@app.route("/itinerarios", methods=["GET"])
def consultar():
    destino = unidecode.unidecode(request.args.get("destino").lower().strip())
    data = request.args.get("data")
    porto = request.args.get("porto")
    
    resultados = [
        {
            "id": it["id"],
            "destino": it["destino"],
            "data": it["data"],
            "navio": it["navio"],
            "porto_embarque": it["porto_embarque"],
            "lugares": it["lugares"],
            "noites": it["noites"],
            "valor": it["valor"],
            "cabines_disponiveis": it["cabines_disponiveis"]
        }
        for chave, it in itinerarios.items()
        if (not destino or chave == destino) and
           (not data or it["data"] == data) and
           (not porto or it["porto_embarque"] == porto)
    ]
    return jsonify(resultados)

if __name__ == '__main__':
    app.run(debug=True, port=5001)