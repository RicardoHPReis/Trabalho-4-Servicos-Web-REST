from flask import Flask, request, jsonify
import shared.utils as utils
import datetime
import requests
import random
import pika
import uuid
import json

app = Flask(__name__)
chave_privada_pagamento = utils.chave_privada()
pagamentos = utils.carregar_dados('./json/pagamentos.json')

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue="pagamento-aprovado", durable=True)
channel.queue_declare(queue="pagamento-recusado", durable=True)


@app.route("/pagamento", methods=["POST"])
def gerar_pagamento():
    data = request.json
    reserva_id = data["reserva_id"]
    pagamento_id = f"PAG-{str(uuid.uuid4().hex[:8].upper())}"
    assinatura = utils.assinar_mensagem(chave_privada_pagamento, reserva_id)
    link = f"http://localhost:5005/externo/{pagamento_id}"

    pagamento = {
        "pagamento_id": pagamento_id,
        "reserva_id": reserva_id,
        "valor": data["valor"],
        "cliente_id": data["cliente_id"],
        "horario": datetime.datetime.now().isoformat(),
        "assinatura": assinatura.hex(),
        "status": "pendente"
    }
    pagamentos = utils.adicionar_dado('./json/pagamentos.json', pagamento_id, pagamento)
    print(f"Pagamento gerado: {pagamento_id} para reserva {data['reserva_id']}")

    response = requests.post("http://localhost:5004/pagamento_externo", json={
        "pagamento_id": pagamento_id,
        "callback_url": f"http://localhost:5002/webhook",
        "reserva_id": data["reserva_id"],
        "valor": data["valor"],
        "client_id": data["client_id"]
    })

    return jsonify({"link_pagamento": link})


@app.route("/processar/<pagamento_id>", methods=["GET"])
def processar_pagamento(pagamento_id):
    if pagamento_id not in pagamentos:
        return jsonify({"erro": "Pagamento não encontrado"}), 404

    aprovado = random.choice([True, False])
    status = "aprovado" if aprovado else "recusado"
    pagamentos[pagamento_id]["status"] = status
    
    print(f"[{status.upper()}] Pagamento {pagamento_id} para reserva {pagamentos[pagamento_id]['reserva_id']}")
    assinatura = utils.assinar_mensagem(chave_privada_pagamento, pagamentos[pagamento_id]["reserva_id"])
    
    evento = {
        "reserva_id": pagamentos[pagamento_id]["reserva_id"],
        "cliente_id": pagamentos[pagamento_id]["cliente_id"],
        "assinatura": assinatura.hex()
    }

    fila = "pagamento-aprovado" if status == "aprovado" else "pagamento-recusado"
    channel.basic_publish(
        exchange='',
        routing_key=fila,
        body=json.dumps(evento),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    
    return jsonify({"status": status}), 200

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    pagamento_id = data["pagamento_id"]
    status = data["status"]
    
    if pagamento_id in pagamentos:
        pagamentos[pagamento_id]["status"] = status
        
        # Publica evento correto
        fila = "pagamento-aprovado" if status == "aprovado" else "pagamento-recusado"
        channel.basic_publish(
            exchange='',
            routing_key=fila,
            body=json.dumps({
                "reserva_id": pagamentos[pagamento_id]["reserva_id"],
                "client_id": pagamentos[pagamento_id]["client_id"]
            }),
            properties=pika.BasicProperties(delivery_mode=2)
        )
        return jsonify({"status": "recebido"})
    return jsonify({"erro": "Pagamento não encontrado"}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5002)