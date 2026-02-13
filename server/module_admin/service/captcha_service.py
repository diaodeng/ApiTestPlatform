# from PIL import Image, ImageDraw, ImageFont
# import io
# import os
# import random
# import base64
#
#
# class CaptchaService:
#     """
#     验证码模块服务层
#     """
#
#     @classmethod
#     def create_captcha_image_service(cls):
#         # 创建空白图像
#         image = Image.new('RGB', (160, 60), color='#EAEAEA')
#
#         # 创建绘图对象
#         draw = ImageDraw.Draw(image)
#
#         # 设置字体
#         font = ImageFont.truetype(os.path.join(os.path.abspath(os.getcwd()), 'assets', 'font', 'Arial.ttf'), size=30)
#
#         # 生成两个0-9之间的随机整数
#         num1 = random.randint(5, 10)
#         num2 = random.randint(0, 5)
#         # 从运算符列表中随机选择一个
#         operational_character_list = ['+', '-', '*']
#         operational_character = random.choice(operational_character_list)
#         # 根据选择的运算符进行计算
#         if operational_character == '+':
#             result = num1 + num2
#         elif operational_character == '-':
#             result = num1 - num2
#         else:
#             result = num1 * num2
#         # 绘制文本
#         text = f"{num1} {operational_character} {num2} = ?"
#         draw.text((25, 15), text, fill='blue', font=font)
#
#         # 将图像数据保存到内存中
#         buffer = io.BytesIO()
#         image.save(buffer, format='PNG')
#
#         # 将图像数据转换为base64字符串
#         base64_string = base64.b64encode(buffer.getvalue()).decode()
#
#         return [base64_string, result]


import base64
import io
import random

import cairocffi as cairo


class CaptchaService:

    @classmethod
    def create_captcha_image_service(cls):
        width, height = 160, 60

        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
        ctx = cairo.Context(surface)

        # 背景
        ctx.set_source_rgb(0.92, 0.92, 0.92)
        ctx.paint()

        # 生成题目
        num1 = random.randint(5, 10)
        num2 = random.randint(0, 5)
        op = random.choice(['+', '-', '*'])

        result = num1 + num2 if op == '+' else num1 - num2 if op == '-' else num1 * num2
        text = f"{num1} {op} {num2} = ?"

        # 字体
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        ctx.set_font_size(28)
        ctx.set_source_rgb(0, 0, 1)

        ctx.move_to(20, 40)
        ctx.show_text(text)

        buffer = io.BytesIO()
        surface.write_to_png(buffer)

        base64_string = base64.b64encode(buffer.getvalue()).decode()
        return [base64_string, result]
