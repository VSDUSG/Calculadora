# Daikon — imagem para hospedar na nuvem (Render, Railway, Fly.io, VPS…)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Dados (banco, imagens, laudos) ficam no disco persistente montado em /dados
ENV DAIKON_DADOS=/dados
ENV DAIKON_NUVEM=1
ENV PORT=8000
EXPOSE 8000

CMD ["python", "run.py"]
