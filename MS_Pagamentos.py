from flask import Flask, request, jsonify
import shared.utils as utils
import datetime
import requests
import random
import pika
import uuid
import json

app = Flask(__name__)
chave_publica_pagamento = utils.chave_publica()
pagamentos = utils.carregar_dados('./json/pagamentos.json')

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()

channel.queue_declare(queue="pagamento-aprovado", durable=True)
channel.queue_declare(queue="pagamento-recusado", durable=True)


@app.route("/pagamento", methods=["POST"])
def gerar_pagamento():
    data = request.json
    reserva_id = data['reserva_id']
    pagamento_id = f"PAG-{str(uuid.uuid4().hex[:8].upper())}"
    utils.adicionar_dado('./json/pagamentos.json', pagamento_id, data)

    pagamento = {
        "pagamento_id": pagamento_id,
        "reserva_id": reserva_id,
        "valor": data.get("valor"),
        "client_id": data.get("client_id"),
        "horario": datetime.datetime.now().isoformat(),
        "status": "pendente"
    }
    pagamentos = utils.adicionar_dado('./json/pagamentos.json', pagamento_id, pagamento)
    print(f"Pagamento gerado: {pagamento_id} para reserva {data.get('reserva_id')}")

    response = requests.post("http://localhost:5004/pagamento_externo", json={
        "pagamento_id": pagamento_id,
        "callback_url": f"http://localhost:5002/webhook",
        "reserva_id": data["reserva_id"],
        "valor": data["valor"],
        "client_id": data["client_id"]
    })
    link = response.json().get('link_pagamento', '')

    return jsonify({"link_pagamento": link})


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    print("[Webhook recebido]", data)  # 👈 ADICIONE ISSO

    pagamento_id = data["pagamento_id"]
    reserva_id = data["reserva_id"]
    client_id = data["client_id"]
    assinatura = data["assinatura"]
    status = data["status"]

    pagamentos = utils.carregar_dados('./json/pagamentos.json')
    
    if pagamento_id not in pagamentos:
        print("[ERRO] Pagamento não encontrado:", pagamento_id)
        return jsonify({"erro": "Pagamento não encontrado"}), 404
    
    pagamentos[pagamento_id]["status"] = status
    utils.salvar_dados("./json/pagamentos.json", pagamentos)

    fila = "pagamento-aprovado" if status == "aprovado" else "pagamento-recusado"
    channel.basic_publish(
        exchange='',
        routing_key=fila,
        body=json.dumps({
            "reserva_id": reserva_id,
            "client_id": client_id,
            "assinatura": assinatura,
            "status": status,
        }),
        properties=pika.BasicProperties(delivery_mode=2)
    )
    print(f"[Fila {fila}] publicada com sucesso para {reserva_id}")
    return jsonify({"status": "recebido"}), 200

    

if __name__ == '__main__':
    app.run(debug=True, port=5002)