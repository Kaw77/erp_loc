import bcrypt

def hash_senha(senha):
    return bcrypt.hashpw(senha.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_senha(senha, hash_armazenado):
    return bcrypt.checkpw(senha.encode('utf-8'), hash_armazenado.encode('utf-8'))