import os
import io
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# 硬编码从加密脚本中拿到的密钥 (32字节 hex)
# 极客做法：如果你用 Nuitka 编译此程序，这串字符会被直接编译成机器码，极难被提取
APP_SECRET_KEY = bytes.fromhex("d97e3640af7ce850ce8ce93b10786aa00ea55b9ebffbfb4a3e0d488804a3df3a")

class SkillManager:
    def __init__(self, dat_dir, key):
        self.dat_dir = dat_dir
        self.aesgcm = AESGCM(key)

    def load_skill_to_memory(self, skill_name) -> io.StringIO:
        """
        核心物理隔离点：解密目标二进制文件，并将其直接转化为内存中的普通文本流。
        全程不写盘，不产生任何临时文件。
        """
        dat_path = os.path.join(self.dat_dir, f"{skill_name}.dat")
        if not os.path.exists(dat_path):
            raise FileNotFoundError(f"找不到技能组件: {skill_name}")
            
        with open(dat_path, 'rb') as f:
            raw_data = f.read()
            
        # 拆分出前 12 字节的 Nonce 和后面的密文
        nonce = raw_data[:12]
        ciphertext = raw_data[12:]
        
        try:
            # 内存中解密为明文 bytes
            decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            # 解码为明文 string
            decrypted_text = decrypted_bytes.decode('utf-8')
            
            # 完美收苞：灌入内存流，返回一个伪装成文件的内存对象
            return io.StringIO(decrypted_text)
        except Exception as e:
            raise PermissionError("解密失败！密钥错误或文件已被篡改。") from e

# --- 模拟 Agent 运行时调用 ---
if __name__ == "__main__":
    # 初始化技能管理器
    manager = SkillManager(dat_dir="./app_data", key=APP_SECRET_KEY)
    
    try:
        # 1. 运行时秘密加载 slurm_expert 技能，直接在内存中读取
        # 用户在硬盘上完全找不到明文，但程序通过 memory_file 拿到了句柄
        memory_file = manager.load_skill_to_memory("SKILL")
        
        # 2. 从内存流中把隐藏的 Prompt 设定提取出来
        system_prompt = memory_file.read()
        memory_file.close() # 显式关闭，内存释放，彻底无痕
        
        # 3. 组装给大模型接口（这里以标准 OpenAI-like SDK 结构为例）
        messages = [
            {"role": "system", "content": system_prompt}, # 你的高价值 md 提示词完美的融入了这里
            {"role": "user", "content": "帮我看看为什么节点一直显示 inval 状态？"}
        ]
        
        print("[*] 内存解密成功，已成功将黑盒 Skills 注入大模型消息队列。")
        print(f"[Debug] 注入的 System Prompt 长度为: {len(system_prompt)} 字符。")
        
    except Exception as e:
        print(f"[-] 发生错误: {e}")
