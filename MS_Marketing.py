from flask import Flask, request, jsonify
import shared.utils as utils
import datetime
import pika
import json
import uuid

app = Flask(__name__)

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue="promocoes", durable=True)


@app.route("/promocao", methods=["POST"])
def publicar_promocao():
    data = request.json
    promocao_id = f"PRM-{str(uuid.uuid4().hex[:8].upper())}"
    promocao = {
        "id": promocao_id,
        "titulo": data["titulo"],
        "descricao": data["descricao"],
        "destino": data["destino"],
        "desconto": data["desconto"]
        #"horario": datetime.datetime.now().isoformat()
    }
    utils.adicionar_dado('./json/promcoes.json', promocao_id, promocao)

    channel.basic_publish(
        exchange='',
        routing_key="promocoes",
        body=json.dumps(promocao),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    return jsonify({"mensagem": "Promoção publicada", "id": promocao_id}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5003)
