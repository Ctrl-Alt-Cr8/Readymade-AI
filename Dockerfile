# Use an official Python runtime as the base image
FROM python:3.12

# Set the working directory
WORKDIR /app

# Copy the project files into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set environment variables
ENV TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}

# Run the bot
CMD ["python", "telegram_bot.py"]
