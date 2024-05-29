import main
from flask import Flask, request


app = Flask(__name__)


@app.route('/', methods=['POST'])
def invoke():
    data = request.get_json()
    return main.main(data)


app.run(host='0.0.0.0')
