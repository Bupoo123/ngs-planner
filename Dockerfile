FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

WORKDIR /app

# 先拷贝依赖文件以利用层缓存
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r /app/requirements.txt

# 拷贝项目代码与资源
COPY app.py /app/app.py
COPY main.py /app/main.py
COPY src/ /app/src/
COPY templates/ /app/templates/
COPY attachments/ /app/attachments/
COPY ref/ /app/ref/
COPY schemas/ /app/schemas/
COPY README.md /app/README.md

# 输出目录（也可通过volume挂载）
RUN mkdir -p /app/output /app/uploads

EXPOSE 5123

CMD ["python", "app.py"]

