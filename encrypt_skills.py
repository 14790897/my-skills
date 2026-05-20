import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def encrypt_all_skills(source_dir, target_dir):
    # 1. 生成或指定一个 32 字节（256位）的 AES 密钥
    
    # 商业发布时，这个密钥应该被写死或混淆在你编译后的主程序中
    # 这里的 hex 字符串就是你要硬编码到主程序里的密钥
    key = AESGCM.generate_key(bit_length=256)
    print(f"[!] 请复制并硬编码此密钥到主程序中 (HEX 格式):\n{key.hex()}\n")
    
    aesgcm = AESGCM(key)
    
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
        
    for filename in os.listdir(source_dir):
        if filename.endswith('.md'):
            source_path = os.path.join(source_dir, filename)
            # 更改后缀为 .dat 混淆视听
            target_filename = filename.replace('.md', '.dat')
            target_path = os.path.join(target_dir, target_filename)
            
            with open(source_path, 'r', encoding='utf-8') as f:
                plaintext_data = f.read().encode('utf-8')
            
            # 生成 12 字节的随机初始化向量 (Nonce)
            nonce = os.urandom(12)
            
            # 执行 AES-256-GCM 加密
            ciphertext = aesgcm.encrypt(nonce, plaintext_data, None)
            
            # 将 nonce 和密文拼接在一起写入 .dat 文件
            with open(target_path, 'wb') as f:
                f.write(nonce + ciphertext)
                
            print(f"[+] 已加密: {filename} -> {target_filename}")

if __name__ == "__main__":
    encrypt_all_skills("./daily-report", "./app_data")
