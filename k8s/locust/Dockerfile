FROM python:3.11-slim

WORKDIR /locust

# Install Locust
RUN pip install --no-cache-dir locust==2.17.0

# Copy locustfile
COPY locustfile.py .

# Expose Locust web UI port
EXPOSE 8089

# Run Locust
ENTRYPOINT ["locust"]
