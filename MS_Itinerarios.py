from flask import Flask, request, jsonify
import shared.utils as utils
import threading
import pika
import json

app = Flask(__name__)

itinerarios = utils.carregar_dados("./json/itinerarios.json")

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

def callback(ch, method, properties, body):
    msg = json.loads(body)
    tipo = method.routing_key
    itinerario_id = msg["itinerario_id"]
    
    if tipo == "reserva-criada":
        for it in itinerarios.keys():
            if it == itinerario_id:
                it["cabines_disponiveis"] -= int(msg["cabines"])
                utils.atualizar_dado("./json/itinerarios.json", itinerarios)
    elif tipo == "reserva-cancelada":
        for it in itinerarios.keys():
            if it == itinerario_id:
                it["cabines_disponiveis"] += int(msg["cabines"])
                utils.atualizar_dado("./json/itinerarios.json", itinerarios)

def start_consumer():
    channel.queue_declare(queue="reserva-criada", durable=True)
    channel.queue_declare(queue="reserva-cancelada", durable=True)

    channel.basic_consume("reserva-criada", callback, auto_ack=True)
    channel.basic_consume("reserva-cancelada", callback, auto_ack=True)

    channel.start_consuming()


threading.Thread(target=start_consumer, daemon=True).start()


@app.route("/itinerarios", methods=["POST"])
def consultar():
    dados = request.json
    destino = dados.get("destino")
    data = dados.get("data_embarque")
    porto = dados.get("porto_embarque")

    resultados = [
        {
            "id": it["id"],
            "data": it["data_embarque"],
            "navio": it["navio"],
            "porto_embarque": it["porto_embarque"],
            "lugares": it["lugares_visitados"],
            "noites": it["noites"],
            "valor": it["valor"],
            "cabines_disponiveis": it["cabines_disponiveis"]
        }
        for it in itinerarios
        if (not destino or it["destino"] == destino) and
           (not data or it["data_embarque"] == data) and
           (not porto or it["porto_embarque"] == porto)
    ]

    return jsonify(resultados)


if __name__ == '__main__':
    app.run(debug=True, port=5001)