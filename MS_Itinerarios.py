from flask import Flask, request, jsonify
import shared.utils as utils
import threading
import pika
import json

app = Flask(__name__)

# Banco de dados em memória
itinerarios_db = [
    {
        "id": "it1",
        "destino": "Bahamas",
        "data_embarque": "2025-08-01",
        "porto_embarque": "Miami",
        "navio": "Sea Explorer",
        "lugares_visitados": ["Nassau", "CocoCay"],
        "noites": 5,
        "valor": 2000,
        "cabines_disponiveis": 10
    },
    {
        "id": "it2",
        "destino": "Mediterrâneo",
        "data_embarque": "2025-08-10",
        "porto_embarque": "Barcelona",
        "navio": "Ocean Spirit",
        "lugares_visitados": ["Roma", "Atenas", "Santorini"],
        "noites": 7,
        "valor": 3200,
        "cabines_disponiveis": 8
    }
]

# Conexão com RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

def callback(ch, method, properties, body):
    event = json.loads(body)
    tipo = method.routing_key
    
    if tipo == "reserva-criada":
        for it in itinerarios_db:
            if it["id"] == event["itinerario_id"]:
                it["cabines_disponiveis"] -= len(event["passageiros"])
    elif tipo == "reserva-cancelada":
        for it in itinerarios_db:
            if it["id"] == event["itinerario_id"]:
                it["cabines_disponiveis"] += len(event["passageiros"])

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
        for it in itinerarios_db
    ]

    return jsonify(resultados)


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
        for it in itinerarios_db
        if (not destino or it["destino"] == destino) and
           (not data or it["data_embarque"] == data) and
           (not porto or it["porto_embarque"] == porto)
    ]

    return jsonify(resultados)


if __name__ == '__main__':
    app.run(debug=True, port=5001)