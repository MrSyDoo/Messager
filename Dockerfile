FROM python:3.10.6

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app/

# Update package lists and upgrade existing packages
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y ffmpeg && \
    pip install --upgrade pip && \
    pip install -U telethon && \
    pip install -r requirements.txt

# Command to run when the container starts
CMD ["bash", "run.sh"]
