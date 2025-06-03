from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend

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