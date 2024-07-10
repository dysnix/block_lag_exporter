# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm

# Set the working directory in the container to /app
WORKDIR /app

# Add Pipfile and Pipfile.lock to the WORKDIR
ADD Pipfile Pipfile.lock /app/

RUN apt-get update && apt-get -y install gcc && \
    pip install pipenv && pipenv install --system --deploy && \
    apt-get -y remove gcc && apt-get -y autoremove

# Add the rest of the code
ADD ./exporter/ /app/

CMD [ "python3", "main.py" ]
