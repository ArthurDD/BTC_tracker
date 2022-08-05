#!/bin/bash


VENV_PATH="./venv/bin/activate"
GRAPH_PATH="./doctest-output/"

# Activate the venv
activate () {
  . $VENV_PATH
}

# Set up the venv
set_up_venv () {
  python3 -m venv venv
  echo "Virtual Environment created! Installing requirements..."
  activate
  pip install -r requirements.txt

  # Since it is the first time the app will be launched, database will be created so we need to migrate
  python website/manage.py migrate
}

if [ -f ./credentials.json ]
then
    echo "Credentials.json file found."
else
    echo "credentials.json missing from the directory. Creating an empty one."
    echo {} > ./credentials.json
fi


if [ -f $VENV_PATH ]
then
    echo "Virtual Environment found. Activating it..."
    activate
else
    echo "Virtual Environment not found. Creating it.."
    set_up_venv
fi


# Delete old graphs from the graph folder
find $GRAPH_PATH -maxdepth 1 -type f -delete

# Start the app
python website/manage.py runserver 0.0.0.0:8000
