from bottle import run, template, get, post, request
import json
import io


@get('/hello')
def index():
    return '<b>Hello World</b>!'


@post('/hello')  # or @route('/login', method='POST')
def say_hello():
    print("received request")
    if type(request.body == io.BytesIO):
        print("processing byte stream")
        print(request.body)
        request.body.seek(0)
        print(request.body)
        name = json.load(request.body).get("name", "oooooooops")
        print("printing name")
        print(name)
    else:
        name = json.loads(request.body).get("name", "oooooooops")
        print("printing name")
        print(name)
        print("print resp")
        print(request.json())

    return template('Hello {{name}}, how are you?', name=name)


run(host='localhost', port=8080)
