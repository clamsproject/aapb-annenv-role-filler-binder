FROM ghcr.io/clamsproject/clams-python-opencv4-torch:1.0.9

WORKDIR /app

COPY requirements.txt .

RUN pip3 install -r requirements.txt

COPY . .

# EXPOSE 8501

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

ENTRYPOINT ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]
