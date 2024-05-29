from flask import Flask, request
import docker
import time
import string
import random
import requests
import zipfile
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.utils import secure_filename


app = Flask(__name__)
docker_client = docker.from_env()

functions = {"hello": "61d218f9e501"}


# {<function>: {"port": #, "last_used":<timestamp>}}
running_functions = {}

# Manage containers, kill them after 1 minute of inactivity
scheduler = BackgroundScheduler()
scheduler.start()


def randomString(stringLength):
    letters = string.ascii_letters
    return ''.join(random.choice(letters) for i in range(stringLength))


def kill_inactive():
    print("Checking for inactive functions")
    deletion = []
    for key in running_functions:
        print("Checking {}".format(key))
        delta = datetime.now() - running_functions[key]['last_used']
        if delta.seconds > 60:
            print("Stopping {}".format(key))
            container = (docker_client.containers
                         .get(running_functions[key]['name']))
            container.stop()
            deletion.append(key)
    for key in deletion:
        del running_functions[key]


# Assign ports automatically and remember them.
current_port = 5002


def start_function(function):
    # 1. start container
    string = function + randomString(8)
    global current_port
    docker_client.containers.run(functions[function],
                                 ports={'5000/tcp': current_port},
                                 detach=True, name=string)
    running_functions[function] = {'port': current_port,
                                   'name': string,
                                   'last_used': datetime.now()}
    current_port = current_port + 1
    time.sleep(0.2)


def execute(function, data):
    # 2. make the request
    r = requests.post('http://127.0.0.1:{}/'
                      .format(running_functions[function]['port']),
                      json=data)
    # Update used time to keep it from being stopped
    running_functions[function]['last_used'] = datetime.now()
    return r.json()


@app.route('/invoke/<function>', methods=['POST'])
def invoke(function):
    if function not in running_functions:
        start_function(function)
    output = execute(function, request.get_json())
    return output

# Also add workflow for adding function:
# It builds a container and registers the tag
@app.route("/create_function", methods=['POST', 'PUT'])
def print_filename():
    file = request.files['file']
    filename = secure_filename(file.filename)
    function_name = filename[:-4]
    tag = "default/{}:{}".format(function_name, randomString(8))
    with zipfile.ZipFile(filename, "r") as zip_ref:
        zip_ref.extractall(".")
    image = docker_client.images.build(path=".", tag=tag)
    functions[function_name] = tag
    print (image)
    return functions[function_name]


scheduler.add_job(kill_inactive, 'interval', seconds=15,
                  misfire_grace_time=None, coalesce=True)
app.run(port=5001)

# curl -X POST -F file=@"/home/panos/customfaas/newfunction.zip" http://localhost:5001/create_function
# curl -X POST http://127.0.0.1:5001/invoke/newfunction  -H 'content-type: application/json' -d '{"message":"hello"}'
