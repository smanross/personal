r"""
    Description: Creates an NTLM/SSPI authenticated sample Flask REST API that looks up data in the tasks dictionary and/or adds to it
    Author: Steven Manross

    Adapted From: https://blog.miguelgrinberg.com/post/designing-a-restful-api-with-python-and-flask
        * added NTLM auth to that example
        * added POSTs to it
        * implemented waitress as the wsgi server
        * implemented logging in preparation for using this script as an imported module for a python service

    Notes:
        * flask-sspi (NT Authentication) needs updates in the _common.py centered around the flask import for newer versions:
            https://github.com/ceprio/flask-sspi/issues/4
        * As well, the flask_sspi._common._get_user_name() function was updated to allow for fully qualified usernames to
              appear (DOMAIN\username)
            * defaulting _get_user_name() to try getting DOMAIN\username first, as part of the username (where available)
                and then fall back to just username:
                    win32api.GetUserNameEx(win32api.NameSamCompatible)
        * This is somewhat similar to the "bottle" version I initially tried with (but couldnt get NTLM AUTH implemented with)
"""
import os
import sys
import urllib
import datetime
from flask import Flask, make_response, jsonify, request, g, url_for
from flask_negotiate import consumes, produces
from flask_sspi import authenticate
from waitress import serve
from regedits import get_registry_value


__console__ = False  # if its runnning as a service, change it to False, or ipython or script file = True
__flask_app_name__ = "flask-test-rest-api"
__flask_proto__ = "http"
__flask_host__ = "0.0.0.0"
__flask_port__ = 8080
__flask_secret_key__ = os.urandom(24).hex()
__service_name__ = "flask-task-rest-api"
__display_name__ = "Flask task REST API"
__description__ = "Python based Flask WSGI server (REST API) for task info"

api_prefix = "/api/v1.0"

log_file = f'{datetime.datetime.now().strftime("%Y-%m-%d--%H-%M-%S.%f")}-requests.log'

if __console__ is not True:
    # running as service, no stdout or stderr are possible
    sys.stdout = open(os.devnull, "a+")
    sys.stderr = open(os.devnull, "a+")
else:
    # ipython or command line script
    print("running as console app")

if __console__:
    print(f"module path = {os.path.dirname(__file__)}")


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)


def get_site_links(app):
    # https://stackoverflow.com/questions/13317536/get-list-of-all-routes-defined-in-the-flask-app
    log_it("get_site_links")
    links = []
    for rule in app.url_map.iter_rules():
        # Filter out rules we can't navigate to in a browser
        # and rules that require parameters
        if "GET" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append({"method": "GET", "url": url, "endpoint": rule.endpoint})
        if "POST" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append({"method": "POST", "url": url, "endpoint": rule.endpoint})
        if "PUT" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append({"method": "PUT", "url": url, "endpoint": rule.endpoint})
        if "UPDATE" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append({"method": "UPDATE", "url": url, "endpoint": rule.endpoint})
        if "DELETE" in rule.methods and has_no_empty_params(rule):
            url = url_for(rule.endpoint, **(rule.defaults or {}))
            links.append({"method": "DELETE", "url": url, "endpoint": rule.endpoint})

    return links


def log_it(message: str, log_level: str = "INFO", line_terminator="\n", timestamp=True):
    r"""
        message: (str) the message you want to log
        log_level: (str) INFO|WARN|DEBUG|ERROR
        line_terminator: (str) typically \n or \r\n (default: \n)
        log_path: (str) default c:\scripts\python-services
        timestamp: (bool) True | False to display a timestamp on the log entry line or not

        log to file for the service stuff since services hate stdout / stderr
    """
    usernm = g.current_user
    global log_file
    try:
        (log_path_value, reg_typ_string) = get_registry_value(
            key=f"System\\CurrentControlSet\\services\\{__service_name__}",
            val_name="LogPath",
            hive_string="HKEY_LOCAL_MACHINE",
        )
        log_path = log_path_value
    except Exception:
        cwd = os.path.abspath(__file__)
        log_path = f"{cwd}\\logs"  # this should get changed by the flask_service.py code

    entry = f"{log_level} - {usernm} - {message}"
    if timestamp is True:
        entry = f'[{datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")}] {entry}'

    if __console__:
        print(entry)
    else:
        entry += line_terminator
        try:
            os.makedirs(f"{log_path}", exist_ok=True)
            with open(f"{log_path}\\{log_file}", "a") as f:
                f.write(entry)
        except Exception:
            pass

    return True


app = Flask(__flask_app_name__)
app.secret_key = __flask_secret_key__

if __console__:
    print(f"secret key: {__flask_secret_key__}")

tasks = [
    {
        "id": 1,
        "title": u"Buy groceries",
        "description": u"Milk, Cheese, Vegetables, Fruit, Tylenol, and Paper towels",
        "depends_on": [],
        "done": True,
    },
    {
        "id": 2,
        "title": u"Learn Python",
        "description": u"Need to find a good Python tutorial on the web",
        "depends_on": [1],
        "done": False,
    },
    {
        "id": 3,
        "title": u"Create a Windows Service for REST API calls",
        "description": u"Does anyone know a modular web service framework that runs on Microsoft Windows, and can support Windows Authentication that might be suited for the task? :)",
        "depends_on": [2],
        "done": False,
    }
]
current_id = len(tasks)


@app.route(f"{api_prefix}/tasks/", methods=["GET"])
@app.route(f"{api_prefix}/tasks/<int:task_id>", methods=["GET"])
@produces("application/json")
@authenticate  # authenticate decorator needs to be closest to function
def get_tasks(task_id: int = 0):
    """
        GET tasks (all, or a single task_id)
    """
    try:
        log_it(f"{request.method} {request.path} user: {g.current_user}, task id: {task_id}")
        filtered_tasks = [task_dict for task_dict in tasks if task_dict["id"] == task_id]
        if task_id > 0:
            return returnable_data(json_data={"tasks": filtered_tasks})
        else:
            return returnable_data(json_data={"tasks": tasks})
    except Exception as e:
        return returnable_data(status_code=500, status="error", description=f"{e}", json_data={})


@app.route(f"{api_prefix}/tasks/", methods=["POST"])
@consumes("application/json")
@produces("application/json")
@authenticate  # authenticate decorator needs to be closest to function
def post_tasks():
    """
        POST tasks (create a new task)
    """
    data = parse_data(request.data)
    log_it(f"{request.method} {request.path} - data = {data}")
    title = get_data_from_dict(data, "title")
    desc = get_data_from_dict(data, "description")
    done = get_data_from_dict(data, "done", "bool")

    global current_id
    new_id = 0
    if desc and title:
        new_id = current_id + 1
        new_entry = {"id": new_id, "title": title, "description": desc, "done": done}
        tasks.append(new_entry)
        current_id = new_id
        log_it(f"added entry: id = {current_id}")
    else:
        return returnable_data(status_code=400, status="error", description="unable to add to tasks: description or title missing")

    return returnable_data(json_data={"id": new_id})


@app.errorhandler(404)
@authenticate  # authenticate decorator needs to be closest to function
def serve_404(e):
    """
        GET, HEAD, POST, PUT if we don"t serve the page from the views above, return an HTTP 404
    """
    # defining function
    log_it(f"page not found: {request.method} -> {request.path}: {e}")
    try:
        links = get_site_links(app)
        log_it(f"available links: {links}")
    except Exception:
        log_it(f"Exception getting links: {e}")

    return returnable_data(status="error", status_code=404, description="REST API url not found")


def get_data_from_dict(data_dict, key, key_type="string"):
    """
        get data from a dictionary, and or return default data for a particular type
    """
    if key in data_dict.keys():
        return data_dict[key]
    else:
        if key_type in ["string", "str"]:
            return ""
        elif key_type in ["integer", "int"]:
            return 0
        elif key_type in ["boolean", "bool"]:
            return False


def parse_data(data):
    """
        parse the request.data to a dictionary
    """
    params_dict = {}
    for parm in urllib.parse.parse_qsl(data):  # tuple
        params_dict[parm[0].decode("utf-8")] = parm[1].decode("utf-8")

    return params_dict


def returnable_data(description="", json_data=None, status="success", status_code=200):
    """
        helper function to massage data to a json response and set the status_code correctly
    """
    data = {}
    try:
        data = {
            "status": status,
            "requested_method": request.method,
            "requested_by": g.current_user,
            "status_description": description,
            "status_code": status_code,
            "url": request.path,
            "json": json_data or {}
        }
        resp = make_response(jsonify(data))
        resp.status_code = status_code

    except Exception as e:
        log_it(f"returnable data Exception: {e}")
        data = {
            "status": "error",
            "requested_method": request.method,
            "requested_by": g.current_user,
            "status_description": "error returning data: the operation completed, but failed to return useful data to the client",
            "status_code": 500,
            "url": request.path,
            "json": json_data or {}
        }
        resp = make_response(jsonify(data))
        resp.status_code = 500

    return resp


if __name__ == "__main__":
    # waitress.serve()
    serve(app, host=__flask_host__, port=__flask_port__)
    # default flask app.run has too many stdout/stderr calls: app.run(debug=True)
