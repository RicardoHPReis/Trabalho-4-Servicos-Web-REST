from flask import Flask, request, jsonify
import shared.utils as utils
import threading
import requests
import random
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

    threading.Thread(target=processar_pagamento, args=(callback_url, pagamento_id, reserva_id, client_id)).start()
    return jsonify({"link_pagamento": f"http://localhost:5004/pagar/{pagamento_id}"})


def processar_pagamento(callback_url, pagamento_id, reserva_id, client_id):
    aprovado = random.choice([True, False])
    status = "aprovado" #if aprovado else "recusado"
    assinatura = utils.assinar_mensagem(chave_privada_pagamento, client_id)

    requests.post(callback_url, json={
        "pagamento_id": pagamento_id,
        "reserva_id": reserva_id,
        "client_id": client_id,
        "assinatura": assinatura.hex(),
        "status": status
    })


@app.route("/pagar/<pagamento_id>", methods=["GET"])
def visualizar_pagamento(pagamento_id):
    return f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Pagamento Recebido</title>
        <meta http-equiv="refresh" content="3;url=http://localhost:5000/reservar">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: #f0f8ff;
                display: flex;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }}
            .box {{
                background: white;
                padding: 40px;
                border-radius: 12px;
                box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
                text-align: center;
                max-width: 500px;
            }}
            h1 {{
                color: #1e90ff;
                margin-bottom: 20px;
            }}
            p {{
                font-size: 18px;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <div class="box">
            <h1>Pagamento {pagamento_id} recebido!</h1>
            <p> Processando... Aguarde a confirmação no sistema.</p>
            <p>Você será redirecionado em instantes...</p>
        </div>
    </body>
    </html>
    """


if __name__ == "__main__":
    app.run(debug=True, port=5004)