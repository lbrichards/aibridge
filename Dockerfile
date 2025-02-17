FROM python:3.12-slim

WORKDIR /app

RUN pip install fastapi uvicorn websockets

COPY app.py .

EXPOSE 51753

CMD ["python", "app.py"]
