FROM python:3.8-slim

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt

RUN python3 -c "import torch; print(torch.cuda.is_available()); import easyocr; easyocr.Reader(['en'], gpu=True if torch.cuda.is_available() else False)"

COPY . .

EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]