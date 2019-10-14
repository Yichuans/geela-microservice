FROM python:2.7

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# RUN apt update -y
# RUN pip install --upgrade pip

# RUN pip install earthengine-api
# RUN pip install google-api-python-client
# RUN pip install pyCrypto

# # NEED THIS despite being deprecated `ee` still uses it
# RUN pip install --upgrade oauth2client

# INSTALL packages
RUN pip install --no-cache-dir -r requirements.txt

# Make port available to the world outside this container
EXPOSE 5000
CMD ["python","landcover.py"]