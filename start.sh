#!/bin/bash

PORT=8000
VENV_PATH="./venv/bin/activate"
GRAPH_PATH="./doctest-output/"  # Please don't change it here without changing it in the code as well (in the headers of graph_visualisation.py)


# Activate the venv
activate () {
  # shellcheck disable=SC1090
  . $VENV_PATH
}


# Set up the venv
set_up_venv () {
    if [ -f $VENV_PATH ]
    then
        echo "Error, virtual environment already existing, use -rv option to reset it instead of -v."
    else
        python3 -m virtualenv ./venv
        echo "Virtual Environment created! Installing requirements..."
        activate
        pip install -r requirements.txt
        echo "Virtual environment set up!"
    fi
}


display_help () {
  echo "Available options:"
  echo "    -app:   Start the web app on the default port 8000, configuring the the virtual environment if necessary. "
  echo "    -p:     Specify the port on which to start the web app."
  echo "    -v:     Create and set up the virtual environment ONLY IF it does not exist. Does not start the app."
  echo "    -rv:    Delete the current virtual environment and set it up again. Does not start the app."
  echo "    -h      Display help page."
}


reset_virtual_env () {
  echo "Resetting virtual environment.."
  rm -rf venv
  set_up_venv
  echo "Virtual environment set up! Web application is now ready to start. (to do so, enter source start.sh)"
}


start_app () {
    echo "Starting web application..."
    if [ -f $VENV_PATH ]
    then
        echo "Virtual Environment found. Activating it..."
        activate
    else
        echo "Virtual Environment not found. Creating it.."
        set_up_venv
    fi

    if [ -f ./credentials.json ]
    then
        pass
    else
        echo "credentials.json missing from the directory. Creating an empty one."
        echo {} > ./credentials.json
    fi

    # Delete old graphs from the graph folder
    find $GRAPH_PATH -maxdepth 1 -type f -delete

    # Start the app
    python3 website/manage.py runserver 0.0.0.0:$PORT
}


if [ $# -eq 0 ]; then
    echo "No arguments provided"
    display_help
fi


while [ -n "$1" ]
do
    case "$1" in
    -app) start=true;;
    -h) display_help
        break;;
    -rv) reset_virtual_env;;
    -p) PORT="$2"
        shift;;
    -v) set_up_venv;;
    *) echo "$1 is not an option"
        break ;;
    esac
    shift
done

if [ "$start" = true ]
then
    start_app
fi

