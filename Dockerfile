FROM python:3.12-slim
ADD ./python /app
# Set the working directory
WORKDIR /app
# Copy the requirements file
COPY requirements.txt /app/requirements.txt
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Run the application
# config_getjudo.py must be mounted to the container at /app/config_getjudo.py
CMD ["python", "getjudo.py"]