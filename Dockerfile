# Python image to use.
FROM python:3.13-alpine

# Set the working directory to /app
WORKDIR /app

# Define the path to the main file
ARG MAIN_FILE_PATH="app/app.py"

# copy the requirements file used for dependencies
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt

# Copy only the necessary application files and directories
COPY app/ app/
COPY data/ data/
COPY csbmdvault/ csbmdvault/

# Run app.py when the container launches
ENTRYPOINT ["gunicorn", "-w", "4", "-b", "0.0.0.0:80", "--chdir", "app", "app:app"]
