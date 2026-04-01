from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

# 1. 2048비트 고강도 암호화 도장 생성
private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2. 텍스트 형태로 변환 (PEM 포맷)
pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

print("\n==== [복사 시작] ====")
print(pem.decode('utf-8').strip())
print("==== [복사 끝] ====\n")