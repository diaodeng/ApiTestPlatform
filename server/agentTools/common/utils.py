import base64
import gzip
import uuid
import zlib


def bs64_to_text(bs64_string):
    """
    将bs64字符串转普通字符串
    :param bs64_string:
    :return:
    """
    string_bytes = bs64_string.encode('utf-8')
    # 使用 base64 模块进行解码
    decoded_bytes = base64.b64decode(string_bytes)
    # 将解码后的字节转换回字符串
    text_string = decoded_bytes.decode('utf-8')
    return text_string

def text_to_bs64(text_string):
    """
    将字符串转bs64
    :param text_string:
    :return:
    """
    # 将字符串转换为字节
    string_bytes = text_string.encode('utf-8')
    # 使用 base64 模块进行编码
    encoded_bytes = base64.b64encode(string_bytes)
    # 将编码后的字节转换回字符串
    bs64_string = encoded_bytes.decode('utf-8')
    return bs64_string

def compress_text(text: str) -> str:
    """
    压缩文本内容
    """
    # print(f"压缩前大小：{len(text)}")
    # 压缩文本
    compressed_data = gzip.compress(text.encode('utf-8'))
    # 使用 base64 编码
    encoded_data = base64.b64encode(compressed_data).decode('utf8')
    # print(f"压缩后大小：{len(encoded_data)}")
    return encoded_data

def decompress_text(encoded_data: str) -> str:
    """
    被压缩后再经过base64编码的数据，先base64解码再解压
    """
    decode_data = base64.b64decode(encoded_data.encode("utf-8"))
    if decode_data.startswith(b'x\x9c'):
        decompress_text = zlib.decompress(decode_data).decode("utf8")
    elif decode_data.startswith(b'x\x1f') or decode_data.startswith(b'\x1f\x8b'):
        decompress_text = gzip.decompress(decode_data).decode("utf-8")
    else:
        raise TypeError("解压失败")
    return decompress_text

def get_mac_address():
    """获取本机ip地址并去掉冒号转换为小写"""
    node = uuid.getnode()
    mac = uuid.UUID(int=node).hex[-12:]
    mac_lower = mac.replace(':', '').lower()
    return mac_lower