from flask import Flask, request, jsonify
import shared.utils as utils
import threading
import requests
import random
import time
import uuid

app = Flask(__name__)
chave_privada_pagamento = utils.chave_privada()

@app.route("/pagamento_externo", methods=["POST"])
def simular_pagamento():
    data = request.json
    pagamento_id = data["pagamento_id"]
    callback_url = data["callback_url"]
    client_id = data["client_id"]
    reserva_id = data["reserva_id"]

    threading.Thread(target=processar_pagamento, args=(pagamento_id, callback_url, reserva_id, client_id)).start()
    return jsonify({"link_pagamento": f"http://localhost:5004/pagar/{pagamento_id}"})


def processar_pagamento(pagamento_id, callback_url, reserva_id, client_id):
    aprovado = random.choice([True, False])
    status = "aprovado" if aprovado else "recusado"

    requests.post(callback_url, json={
        "pagamento_id": pagamento_id,
        "status": status
    })

@app.route("/pagar/<pagamento_id>", methods=["GET"])
def visualizar_pagamento(pagamento_id):
    return f"<h2>Pagamento {pagamento_id} recebido!</h2><p>Processando... Aguarde a confirmação no sistema.</p>"

if __name__ == "__main__":
    app.run(debug=True, port=5004)