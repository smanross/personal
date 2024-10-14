This is a sample windows service broken up into 2 parts
The Flask Service (flask_service.py) has most of all the code in it for Windows Service operations, and an import of "web_flask_code" to handle the rest API framework keeping both parts seperate.

The "flask_web_code\__init__.py" has all the flask pieces and handles the REST API thread to communicate with the client code.

From there, you can call the REST API using the python requests library (NTLM or Negotiate) Authentication because It's been tested using SSPI and Negotiate security.

The client should be able to connect using something similar to this:
```
from requests_negotiate_sspi import requests, HttpNegotiateAuth

requests.get("http://somevm:8080/api/v1.0/tasks/1",
             auth=HttpNegotiateAuth(),
             headers={"Content-Type": "application/json",
                      "Accept": "application/json",
                     }
)
```
While this is the only example currently, the REST API supports GETs and POSTs and will update the task list with new tasks providing the correct data is sent, but the POST data will not set a depends_on value because I didn't update the post_tasks() method to support that.

This was tested as a pyinstaller executable service, and as free-standing python scripts - both running as services.  Special care was made so that both of the scripts could be run at the same time:
 * not both service active at the same time, but both services could be installed as services at the same time (because the REST API for both services would communicate on the same port and that wouldn't work).
