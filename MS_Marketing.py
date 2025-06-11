from flask import Flask, request, jsonify
import shared.utils as utils
import pika
import json
import uuid

app = Flask(__name__)

# Conexão com RabbitMQ
connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue="promocoes", durable=True)


@app.route("/promocao", methods=["POST"])
def publicar_promocao():
    data = request.json
    promocao_id = str(uuid.uuid4())
    evento = {
        "id": promocao_id,
        "titulo": data["titulo"],
        "descricao": data["descricao"],
        "destino": data["destino"],
        "desconto": data["desconto"]
    }

    channel.basic_publish(
        exchange='',
        routing_key="promocoes",
        body=json.dumps(evento),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    return jsonify({"mensagem": "Promoção publicada", "id": promocao_id})


if __name__ == '__main__':
    app.run(debug=True, port=5003)
