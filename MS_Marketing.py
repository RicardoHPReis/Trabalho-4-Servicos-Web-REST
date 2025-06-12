from flask import Flask, request, jsonify
import shared.utils as utils
import json
import pika
import uuid
import os

app = Flask(__name__)
promocoes = utils.carregar_dados('./json/marketing.json')

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='promocoes', durable=True)

@app.route('/api/promocoes', methods=['POST'])
def publicar_promocao():
    nova_promo = request.json
    
    promo_id = f"PROMO-{str(uuid.uuid4().hex[:8].upper())}"
    promocoes[promo_id] = nova_promo
    
    promocoes = utils.adicionar_dado('./json/promocoes.json', promo_id, nova_promo)
    
    channel.basic_publish(
        exchange='',
        routing_key='promocoes',
        body=json.dumps(nova_promo)
    )
    
    return jsonify({
        'status': 'Promoção publicada com sucesso',
        'promo_id': promo_id
    })

# Endpoint para listar promoções
@app.route('/api/promocoes', methods=['GET'])
def listar_promocoes():
    return jsonify(promocoes)

if __name__ == '__main__':
    app.run(debug=True, threaded=True, port=5005)