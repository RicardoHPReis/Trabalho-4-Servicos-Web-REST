from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import json
import os

def chave_privada():
    with open("./secret/MS_Pagamento_privado.pem", "rb") as chave:
        return serialization.load_pem_private_key(
            chave.read(),
            password=None,
            backend=default_backend()
        )

def chave_publica():
    with open("./shared/keys/MS_Pagamento_publico.pem", "rb") as chave:
        return serialization.load_pem_public_key(
            chave.read(),
            backend=default_backend()
        )

def assinar_mensagem(chave_privada, mensagem: str):
    return chave_privada.sign(
        mensagem.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256()
    )
def verificar_assinatura(chave_publica, assinatura, mensagem:str):
    try:
        chave_publica.verify(
            assinatura,
            mensagem.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return True
    except Exception:
        return False


def carregar_dados(caminho) -> dict:
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding='utf-8') as f:
        dados = json.load(f)
    return dados

def salvar_dados(caminho, dados) -> None:
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)

def adicionar_dado(caminho, chave, novos_valores) -> dict:
    dados = carregar_dados(caminho)
    dados[chave] = novos_valores
    salvar_dados(caminho, dados)
    return dados

def atualizar_dado(caminho, chave_inicial, chave, novo_valor):
    dados = carregar_dados(caminho)
    item = dados[chave_inicial]
    item[chave] = novo_valor
    salvar_dados(caminho, dados)
    return dados
    
def deletar_dado(caminho, chave) -> dict:
    dados = carregar_dados(caminho)
    del dados[chave]
    salvar_dados(caminho, dados)
    return dados