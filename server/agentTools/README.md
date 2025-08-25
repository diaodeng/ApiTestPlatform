
## 打包工具 pyinstaller
安装：pip install pyinstaller 

## 打包命令 
首次：pyinstaller --onefile --windowed .\xxx.py 
pyinstaller -F -w --add-data "assets:assets" .\agent_plus.py
设置xxx.spec文件后使用 pyinstaller .\agent_plus.spec打包

打包后需要将config.ini和db目录一起拷贝到dist目录中

## 主题库 ttkbootstrap 
安装：pip install ttkbootstrap
网址：https://ttkbootstrap.readthedocs.io/en/latest/zh/themes/
控制台执行，命令：python -m ttkcreator
