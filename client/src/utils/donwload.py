# -*- coding: utf-8 -*-
# @Time: 2025/8/21 23:20
# @Author: yoyo
# @Email: 569984165@qq.com
# @File: donwload.py
# @Software: PyCharm

import os
import requests
import zipfile


def donwload_file(url, file_name):
    # 下载文件到当前目录
    response = requests.get(url)
    temp_filename = "temp_file"
    with open(temp_filename, "wb") as f:
        f.write(response.content)

    # 解压文件
    try:
        with zipfile.ZipFile(temp_filename, "r") as zip_ref:
            file_in_zip = zip_ref.namelist()[0]
            zip_ref.extractall() #解压到当前目录
    except zipfile.BadZipFile as e:
        print("文件下载失败或不是有效的zip压缩包")
        exit(1)

    # 重命名解压出的文件
    os.rename(file_in_zip, file_name)

    # 清理临时文件
    os.remove(temp_filename)

    print("文件下载成功")