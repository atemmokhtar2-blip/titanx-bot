FROM python:3.11-slim

WORKDIR /home/user/app

RUN pip install --no-cache-dir fastapi uvicorn[standard]

COPY app.py .

ENV GRADIO_SERVER_PORT=7860

EXPOSE 7860

CMD ["python", "app.py"]
