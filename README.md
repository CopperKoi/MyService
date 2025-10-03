# MyService

> 一个简陋个人博客的搭建实例

安装常用工具和Nginx

```bash
apt install -y git curl wget unzip build-essential ufw nginx python3-venv python3-pip
```

![image.png](image.png)

然后创建项目目录，激活nenv，下一些工具和依赖

```bash
mkdir -p ~/projects/blog-backend
cd ~/projects/blog-backend
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install fastapi uvicorn[standard] python-multipart sqlalchemy aiosqlite jose passlib[bcrypt] pydantic sqlalchemy-utils
pip install sqlmodel
```

![image.png](image%201.png)

![image.png](image%202.png)

目录构建

// 我本来有个很宏大的规划，但是code量太大（主要是我懒…）遂放弃

```
/home/copperkoi/projects/blog-backend/
├─ .venv/
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ core.py
│  ├─ models.py
│  ├─ crud.py
│  ├─ auth.py
│  ├─ routers/
│  │   ├─ posts.py
│  │   └─ auth.py
│  └─ uploads/
├─ alembic/
└─ requirements.txt
```

```bash
mkdir -p .venv app/{routers,uploads} alembic && \
touch app/{__init__,main,core,models,crud,auth}.py app/routers/{posts,auth}.py requirements.txt
```

安装依赖

```bash
pip install fastapi uvicorn[standard] sqlmodel python-multipart python-jose passlib[bcrypt] aiofiles python-dotenv Pillow
```

![image.png](image%203.png)

编写main.py（详见/code）

/home/copperkoi/projects/blog-backend/app/main.py

编写env

/home/copperkoi/projects/blog-backend/.env

```
CONTENT_DIR=./content
JWT_SECRET=d15f7e3c9a2b8f4e1c6a9d0b3e8f7c2a5d4e1f9a8b7c6d5e4f3a2b1c0d9e8f7a
JWT_ALGO=HS256
ACCESS_EXPIRE_MINUTES=1440
ADMIN_USER=admin
ADMIN_PASS=K8#mNp3$qRtV9@xY
CORS_ORIGINS=http://localhost:8000,http://copperkoi.cn
```

![image.png](image%204.png)

测试运行

![image.png](image%205.png)

systemd服务

/etc/systemd/system/blog-backend.service

```
[Unit]
Description=Markdown Blog Backend (uvicorn)
After=network.target

[Service]
User=copperkoi
Group=www-data
WorkingDirectory=/home/copperkoi/projects/blog-backend
Environment="PATH=/home/copperkoi/projects/blog-backend/.venv/bin"
EnvironmentFile=/home/copperkoi/projects/blog-backend/.env
ExecStart=/home/copperkoi/projects/blog-backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

![image.png](image%206.png)

启用并启动

```bash
systemctl daemon-reload
systemctl enable --now blog-backend
journalctl -u blog-backend -f
```

![image.png](image%207.png)

编写前端（详见/code）

/var/www/blog/index.html

/var/www/blog/admin.html

nginx配置

/etc/nginx/sites-available/example.com

```
server {
    listen 80;
    server_name copperkoi.cn www.copperkoi.cn;

    # 静态网页
    root /var/www/blog;
    index index.html;

    client_max_body_size 10M;

    location / {
        try_files $uri $uri/ /index.html;
    }

    # 反代 API 到 uvicorn
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_read_timeout 60s;
    }
}
```

![image.png](image%208.png)

启用并测试nginx

```bash
ln -s /etc/nginx/sites-available/copperkoi.cn /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

![image.png](image%209.png)

---

关闭全部进程并自查

```bash
systemctl stop nginx
systemctl stop blog-backend
systemctl list-units --type=service | grep -E 'nginx|blog|uvicorn|gunicorn' || true
ss -ltnp | grep ':8000' || true
nginx -t
ls -l /var/www/blog/index.html /var/www/blog/admin.html
ls -l /home/ubuntu/projects/blog-backend/.env
```

启动后端

```bash
systemctl daemon-reload
systemctl enable --now blog-backend
systemctl status blog-backend --no-pager
journalctl -u blog-backend -f
```

![image.png](image%2010.png)

启动nginx

```bash
systemctl enable --now nginx
systemctl status nginx --no-pager
```

![image.png](image%2011.png)

浏览器访问

![image.png](image%2012.png)

<aside>

**success!!!**

---

Copyright © 2025 CopperKoi

</aside>
