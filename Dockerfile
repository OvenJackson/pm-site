FROM python:3.13-slim
WORKDIR /app
COPY . .
ENV PORT=8080
EXPOSE 8080
CMD ["python", "tools/online_server.py"]