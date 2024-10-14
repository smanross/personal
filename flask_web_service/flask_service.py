r'''
    Generic Waitress/Flask windows service dependent on an imported application module file called flask_web_code

    # install - and set automatic startup
    python c:\scripts\flask_service.py install c:\scripts\python-services\flask_tasks_rest_api --startup=auto

    # remove
    python c:\scripts\flask_service.py remove c:\scripts\python-services\flask_tasks_rest_api

    See handle_command_line() for more examples of the above

    The 3rd argument on the command line is the path for where your flask_web_code files are (the web code is in the form of a python module):
    Example structure of the flask_web_code module:
        c:\scripts\python-services\flask_tasks_rest_api\flask_web_code\__init__.py
    Note: In the example above, the logging directory will be:
        c:\scripts\python-services\flask_tasks_rest_api

    Huge thanks to: https://stackoverflow.com/questions/59893782/how-to-exit-cleanly-from-flask-and-waitress-running-as-a-windows-pywin32-servi

    The concept was that I might have multiple services that all use this same base code, and have a different "flask_web_code" module that builds the flask app and app.routes
'''
import os
import sys
import ctypes
import threading
import datetime
import site
import traceback
import win32serviceutil
import win32service
import servicemanager
import win32event
from regedits import get_registry_value, set_registry_value


__console__ = True  # this will automatically get changed to False if the service starts from this script.  this is only to output info when this is run to start/stop/install/remove the service

command_line_options = ['install', 'update', 'start', 'stop', "restart", "remove"]
command_line_arguments = ["--startup=", "--password=", "--username=", "--perfmonini=", "--perfmondll=", "--interactive", "--wait="]

running_as_frozen_build = False
if getattr(sys, "frozen", False) and hasattr(sys, '_MEIPASS'):
    # frozen_build means pyinstaller EXE
    running_as_frozen_build = True


for win32_dir in [f'{os.path.dirname(sys.executable)}\\Lib\\site-packages\\win32',
                  f'{os.path.dirname(sys.executable)}\\Lib\\site-packages\\pywin32_system32'
                  ]:
    if win32_dir not in site.getsitepackages():
        site.addsitedir(win32_dir)

log_file = f"{datetime.datetime.now().strftime('%Y-%m-%d--%H-%M-%S.%f')}.log"
log_path = None  # this is temporary, and the script below will alter the log_path based on parameters passed in the command line or found in registry


def log_to_file_and_eventlog(message, log_level="INFO", line_terminator="\n", timestamp=True):
    '''
        Log to the log file and the event log
    '''
    # log to the log file
    log_to_file(message, log_level, line_terminator, timestamp)
    # log to the windows event log
    servicemanager.LogInfoMsg(message)

    return True


def log_to_file(message: str, log_level: str = "INFO", line_terminator="\n", timestamp=True):
    r"""
        message: (str) the message you want to log
        log_level: (str) INFO|WARN|ERROR
        line_terminator: (str) typically \n or \r\n (default: \n)
        log_path: (str) default c:\scripts\python-services
        timestamp: (bool) True | False to display a timestamp on the log entry line or not

        log to file for the service stuff since services hate stdout / stderr
    """
    global log_path
    global log_file
    if timestamp is True:
        entry = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')}] {log_level} - {message}"
    else:
        entry = message

    try:
        if log_path is not None:
            os.makedirs(f'{log_path}', exist_ok=True)
            f = open(f"{log_path}\\{log_file}", "a")

            f.write(f'{entry}{line_terminator}')
            f.close()
        if __console__:
            print(entry)
    except Exception:
        return False

    return True


module_dirs = [arg.lower() for arg in sys.argv if arg not in command_line_options and os.path.isdir(arg)]
module_dir = ""
if len(module_dirs) == 1:  # running as python script - module dir is passed in command line
    module_dir = module_dirs[0]
    log_path = f"{module_dir}\\logs"  # you cant log any thing prior to this because it needs to log in the module_dir
    log_to_file(f'adding python site_dir for web code={module_dir}')
    site.addsitedir(module_dir)
elif running_as_frozen_build is True and not len(module_dirs):
    # CWD at this point is in c:\windows\system32\_MEIXXXXXXX
    log_to_file(f'running_as_frozen_build and no module_dirs - setting log path to current_directory: {log_path}')
else:
    log_to_file(f'ERROR -> len of module_dirs = {len(module_dirs)}', log_level="ERROR")
    log_to_file(f'sys.argv = {module_dirs}', log_level="ERROR")
    sys.exit(1)

try:
    from waitress import serve as waitress_serve
except Exception:
    log_to_file('Excepted importing waitress serve function')

try:
    import flask_web_code
    from flask_web_code import app as __app__, __service_name__, __display_name__, __description__, __flask_proto__, __flask_host__, __flask_port__
    if running_as_frozen_build:
        __service_name__ += "-pyinstaller-exe"
        __display_name__ += " (pyinstaller-exe)"
        __description__ += " -- as an exe (using pyinstaller to generate the EXE)"
        flask_web_code.__service_name__ = __service_name__

except Exception as e:
    log_to_file(f'excepted importing flask_web_code (parts): {e}', log_level="ERROR")
    log_to_file(f'     site dirs: {site.getsitepackages()}', log_level="ERROR")
    log_to_file(f'user site dirs: {site.getusersitepackages()}', log_level="ERROR")
    log_to_file(f'path: {sys.path}', log_level="ERROR")
    sys.exit(1)

log_path_value = ""
try:
    (log_path_value, reg_typ_string) = get_registry_value(
        key=f"System\\CurrentControlSet\\services\\{__service_name__}",
        val_name="LogPath",
        hive_string="HKEY_LOCAL_MACHINE",
    )
    if log_path_value:
        log_path = log_path_value
        os.path.makedirs(log_path, exist_ok=True)
        flask_web_code.log_path = log_path
except Exception:
    pass

log_to_file('python web imports are complete - service should be startable')


def getTrace():
    """ retrieve and format an exception into a nice message
    """
    msg = traceback.format_exception(
        sys.exc_info()[0],
        sys.exc_info()[1],
        sys.exc_info()[2]
    )
    msg = ''.join(msg)
    msg = msg.split('\012')
    msg = ''.join(msg)
    msg += '\n'
    return msg


class ServerThread(threading.Thread):
    '''
        Server Thread in order to handle shutting down waitress when a service stop happens
    '''
    def __init__(self):
        threading.Thread.__init__(self)
        try:
            log_to_file(f'native id: {self.native_id}')
        except Exception as _e:
            log_to_file(f'native id Excepted: {_e}')

    def run(self):
        log_to_file('ServerThread: thread start')
        try:
            waitress_serve(__app__, host=__flask_host__, port=__flask_port__, _quiet=True, ipv6=False, url_scheme=__flask_proto__)  # blocking
        except Exception as _e:
            log_to_file(f'ServerThread: exception serving the waitress WSGI server: {_e}')

        log_to_file('ServerThread: thread ended')

    def get_id(self):
        '''
            get the thread ID
        '''
        # returns id of the respective thread
        if hasattr(self, '_thread_id'):
            return self._thread_id
        for thread_id, thread in threading._active.items():
            if thread is self:
                return thread_id

    def exit(self):
        '''
            Close the thread
        '''
        thread_id = self.get_id()
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(SystemExit))
        if res > 1:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
            print('Exception raise failure')


class WindowsService(win32serviceutil.ServiceFramework):
    """ Windows NT Service class for running a flask/waitress server """

    _svc_name_ = __service_name__
    _svc_display_name_ = __display_name__
    _svc_description_ = __description__
    _exe_name_ = sys.executable
    global running_as_frozen_build
    if running_as_frozen_build:
        _exe_args_ = f'"{module_dir}"'
    else:
        _exe_args_ = f'"{os.path.abspath(__file__)}" "{module_dir}"'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.is_stopping = False
        self.server = ServerThread()
        # Create an event which we will use to wait on - The "service stop" request will set this event.
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)

    @classmethod
    def parse_command_line(cls):
        r'''
            Parse the command line options so we can handle non-standard agruments like the python path for the flask_web_code import

            typical command lines (normal python script implementation):
                python <service_script_name> <web_code_import_directory> <options>
                # install
                python c:\scripts\flask_service.py install c:\scripts\python-services\flask_tasks_rest_api
                # install - and set automatic startup
                python c:\scripts\flask_service.py install c:\scripts\python-services\flask_tasks_rest_api --startup=auto

                # remove
                python c:\scripts\flask_service.py remove c:\scripts\python-services\flask_tasks_rest_api

                # start
                python c:\scripts\flask_service.py start c:\scripts\python-services\flask_tasks_rest_api

                # stop
                python c:\scripts\flask_service.py stop c:\scripts\python-services\flask_tasks_rest_api
            typical command lines for pyinstaller:
                name_of_exe.exe <options>

               # install and auto start
               name_of_exe.exe install --startup=auto  (there's an alias for --startup=automatic so that works also)
                   * the logging directory for the service EXE is the "current windows diretory"\logs
                   * there's no need for the directory declaration in the arguments since the pyinstaller includes
                     the flask_web_code module by way of the pathex parameter declared in the spec file

               # remove the service
               name_of_exe.exe remove

               # stop the service
               name_of_exe.exe stop

               # update the startup to manual
               name_of_exe.exe update --startup=manual

        '''
        global command_line_options  # ['install', 'update', 'start', 'stop', "restart", "remove"]
        global command_line_arguments  # ["--startup=", "--password=", "--username=", "--perfmonini=", "--perfmondll=", "--interactive", "--wait="]
        service_cmdline_options = [arg for arg in sys.argv if arg.lower() in command_line_options]
        cmd_line_args = service_cmdline_options.copy()
        # pyinstaller
        # this needs to be added if its running as a script, but not if its running as an EXE
        if running_as_frozen_build:
            log_to_file('running as a pyinstaller frozen build')
        else:
            log_to_file('running as a normal python process')
            cmd_line_args.insert(0, sys.argv[0])  # the python script

        # extra args are what the HandleCommandLine calls options
        extra_args = [arg.lower() for arg in sys.argv if arg.lower() not in cmd_line_args]
        for arg in command_line_arguments:
            for extra_arg in extra_args:
                if arg in extra_arg:
                    # add the options after the script name
                    log_to_file(f"adding to cmd_line_args: {extra_arg}")
                    cmd_line_args.insert(1, extra_arg)

        # print(sys.argv)
        # print(cmd_line_args)
        # print(service_args)
        # sys.exit(0)

        if len(service_cmdline_options) == 1:
            log_to_file('HandleCommandLine: performing service modifications')
            log_to_file(f'HandleCommandLine: args = {cmd_line_args}')
            log_to_file(f'HandleCommandLine: exe_args = {cls._exe_args_}')
            for key, item in cls.__dict__.items():
                log_to_file(f'HandleCommandLine: class dict keys {key} = {item}')
            # the cls allows us to send the _svc_name_ etc from the class because this is a class method
            try:
                log_to_file('HandleCommandLine: b4 win32serviceutil')
                win32serviceutil.HandleCommandLine(cls, argv=service_cmdline_options)
                log_to_file('HandleCommandLine: after win32serviceutil')
            except Exception as e:
                log_to_file(f"Failed performing service maintenance: Exception: {e}")
            log_to_file(f'Service Maintenance complete: {cmd_line_args}')
        elif len(service_cmdline_options) > 1:
            log_to_file_and_eventlog(f"Failed performing service maintenance due to multiple commands being sent: {service_cmdline_options}")
        else:
            global __console__
            __console__ = False
            log_to_file('initializing service')
            servicemanager.Initialize()
            log_to_file('PreparingToHostSingle')
            servicemanager.PrepareToHostSingle(WindowsService)
            log_to_file('Starting Service Dispatcher')
            servicemanager.StartServiceCtrlDispatcher()

    def SvcStop(self):
        '''
            Stop The Service
        '''
        # Before we do anything, tell the SCM we are starting the stop process.
        if not self.is_stopping:
            log_to_file('Reporting Stop Pending')
            self.is_stopping = True
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        log_to_file('Stop Event set')
        # And set my event.
        win32event.SetEvent(self.hWaitStop)

    def SvcShutdown(self):
        '''
            SvcStop only gets triggered when the user explicitly stops (or restarts)
            the service.  To shut the service down cleanly when Windows is shutting
            down, we also need to hook SvcShutdown.
        '''

        # Before we do anything, tell the SCM we are starting the stop process.
        log_to_file('Stop Pending (windows is shutting down)')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)

        # And set my event.
        win32event.SetEvent(self.hWaitStop)
        log_to_file('Stop Event set (windows is shutting down)')

    def SvcDoRun(self):
        '''
            Start service
        '''
        # log a service started message
        log_to_file('Starting Service')
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, self._svc_display_name_))
        self.main()

    def main(self,):
        '''
            Main service code
        '''
        log_to_file('main start')
        self.server = ServerThread()
        self.server.start()
        log_to_file('waiting on win32event')
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        self.server.exit()  # raise SystemExit in inner thread
        log_to_file('waiting on thread')
        self.server.join()
        log_to_file('main done')

        # log a service stopped message
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, self._svc_display_name_))


def set_log_dir():
    log_dir_arg = "--set-log-dir="
    for arg in sys.argv:

        if arg.startswith(log_dir_arg):
            param = arg.replace(log_dir_arg, "")
            # if you send a bad path...  its not currently validated
            set_registry_value(
                key_name=f"System\\CurrentControlSet\\services\\{__service_name__}",
                val_name="logging_path",
                hive_string="HKLM",
                reg_type_string="REG_SZ",
                value=param
            )


def init():
    try:
        control_args = [arg for arg in sys.argv if arg in command_line_options]
        for argv in sys.argv:
            for arg in command_line_arguments:
                if argv.startswith(arg):
                    param = argv[(len(arg) - 1) * -1:].lower()
                    if arg == "--startup=" and param not in ["auto", "manual", "delayed", "disabled"]:
                        if param == "automatic":
                            control_args.insert(0, "--startup=auto")  # im always using "automatic" by accident
                        else:
                            log_to_file(f"init: --startup= param not in approved list: {param}")
                        continue
                    control_args.insert(0, argv)  # the args go before the options or else HandleCommandLine gets confused
                    # and if you try to use HandleCommandLine with errors with the args, the print statements will mess you up
                    # because of all the service limitations on stdout / stderr.

        set_log_dir()
        if len(control_args) > 0:
            control_args.insert(0, sys.executable)  # now add the exe as first arg
            log_to_file(f"main: entering HandleCommandLine for WindowsService (control_args = {control_args})")
            win32serviceutil.HandleCommandLine(WindowsService, argv=control_args)
        elif running_as_frozen_build:
            log_to_file(f"main: Starting WindowsService (frozen build) - args: {sys.argv}")
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(WindowsService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            log_to_file(f"main: Starting WindowsService (as python script) - args = {sys.argv}")
            WindowsService.parse_command_line()
    except Exception as e:
        log_to_file(f"Exception in Main: {e}")
        sys.exit(0)


if __name__ == '__main__':
    init()
