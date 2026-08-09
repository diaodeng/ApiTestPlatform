## 项目开发及发布相关

[//]: # (### 开发)

[//]: # (```bash)

[//]: # (# 克隆项目)

[//]: # (git clone https://gitee.com/insistence2022/RuoYi-Vue3-FastAPI.git)

[//]: # ()
[//]: # (# 进入项目根目录)

[//]: # (cd RuoYi-Vue3-FastAPI)

[//]: # (```)

#### 前端
```bash
# 进入前端目录

# 安装依赖
npm install 或 yarn --registry=https://registry.npmmirror.com

# 建议不要直接使用 cnpm 安装依赖，会有各种诡异的 bug。可以通过如下操作解决 npm 下载速度慢的问题
npm install --registry=https://registry.npmmirror.com

# 启动服务
npm run dev 或 yarn dev
```

#### 后端
```bash
# 进入后端目录

# 安装项目依赖环境
pip3 install -r requirements.txt

# 配置环境
在.env.dev文件中配置开发环境的数据库和redis

# 运行sql文件
1.新建数据库
2.使用命令或数据库连接工具运行sql文件夹下的ruoyi-fastapi.sql

# 运行后端
python3 app.py --env=dev
```

#### 访问
```bash
# 默认账号密码
账号：admin
密码：admin123

# 浏览器访问
地址：http://localhost:80
```

### 发布

#### 前端
```bash
# 构建测试环境
npm run build:stage 或 yarn build:stage

# 构建生产环境
npm run build:prod 或 yarn build:prod
```

#### 后端
```bash
# 配置环境
在.env.prod文件中配置生产环境的数据库和redis

# 运行后端
python3 app.py --env=prod
celery -A config.celery_app.celery_app beat -l info --scheduler config.celery_scheduler:DatabaseScheduler
celery -A config.celery_app.celery_app worker -l info -Q sys,qtr,celery --concurrency=4
```

#### 客户端
```bash
# 打包（zip）
pyinstaller.exe --clean .\QTRClient2.spec --noconfirm
#独立包
pyinstaller.exe --clean .\QTRClient.spec --noconfirm
```
#### uv管理依赖
```bash
uv add fastapi uvicorn  # 增加依赖
uv add --group dev pytest ruff  # 增加依赖到开发环境
uv sync  # 使用uv.lock安装依赖
```

#### 兼容sqlite和内存缓存
```text
DB_TYPE='sqlite'
DB_SQLITE_PATH='caches/qtr-dev.sqlite3'
CACHE_BACKEND='memory'
SQLITE_AUTO_SEED=true

第一次启动会默认插入初始化数据                                                                                                                                                                                                                                    
如果你想要空 SQLite 库，把 SQLITE_AUTO_SEED=false。如果你想强制重导，仍然可以手工跑这个脚本：
                                                                                                                                                                                                                                    
python.exe scripts\seed_sqlite_from_init_sql.py --create-schema --clear-existing 
```