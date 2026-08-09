FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[dashboard,hf]"

EXPOSE 8501
CMD ["streamlit", "run", "src/password_arena/dashboard.py", "--server.address=0.0.0.0"]
