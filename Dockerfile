# Use an official Python runtime as the base image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Copy the project files into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Python path so imports work inside Docker
ENV PYTHONPATH=/app

# Expose the port the app runs on
EXPOSE 8080

# Run the app
CMD ["python", "/app/src/automate_tweets.py"]
