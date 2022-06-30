'''
    Get the elusive QueryInformationW data from the undocumented function for WTS Session Info

    ctypes.Structures and functional issues with my attempted code corrected by: Eryk Sun <email address redacted>
      * Kudos to Eryk Sun and the python-win32 mailing list for helping me get this working in Python
        (and better understanding what it takes to convert C code to python using the ctypes module)

    * It should work on any WTS/RDP Server from 2003 onward (provided you have the WINSTA.DLL in system32 dir, but 
      I only tested it on W2016 so far
'''
import datetime
import ctypes
from ctypes import wintypes
from enum import IntEnum


def get_datetime_from_windows_epoch(epoch:int):
    '''
        Windows Epoch is 1/1/1601 unlike the Unix Epoch at 1/1/1970

        * Never mind the fact that the windows file explorer chokes any time you pass it
          a date prior to 1970 and it says the file date is blank
        * and we wont mention Excel issues with early dates because it was supposedly built
          to be compatible with Lotus 123 which also had date issues with "early dates"
    '''
    windows_date = datetime.datetime.fromtimestamp(epoch / 1e7)  # the division handles miliseconds correctly
    actual_date = windows_date.replace(year=windows_date.year - 369)
    return actual_date

winsta = ctypes.WinDLL('winsta', use_last_error=True)

WINSTATIONNAME_LENGTH = 32
DOMAIN_LENGTH = 17
USERNAME_LENGTH = 20
MAX_THINWIRECACHE = 4

SERVERNAME_CURRENT = None
LOGONID_CURRENT = -1

# WINSTATIONINFOCLASS
WinStationInformation = 8

# WINSTATIONSTATECLASS

class WINSTATIONSTATECLASS(IntEnum):
    '''
       RDP/WTS Connection states
    '''
    Active = 0
    Connected = 1
    ConnectQuery = 2
    Shadow = 3
    Disconnected = 4
    Idle = 5
    Listen = 6
    Reset = 7
    Down = 8
    Init = 9

class TSHARE_COUNTERS(ctypes.Structure):
    '''
        Tshare Counters
    '''
    __slots__ = ()
    _fields_ = (
        ('Reserved', wintypes.ULONG),
    )


class PROTOCOLCOUNTERS(ctypes.Structure):
    '''
        Protocol Counters
    '''
    __slots__ = ()
    class SPECIFIC(ctypes.Union):
        '''
            TShare Specific Counters
        '''
        __slots__ = ()
        _fields_ = (
            ('TShareCounters', TSHARE_COUNTERS),
            ('Reserved', wintypes.ULONG * 100),
        )
    _fields_ = (
        ('WdBytes', wintypes.ULONG),
        ('WdFrames', wintypes.ULONG),
        ('WaitForOutBuf', wintypes.ULONG),
        ('Frames', wintypes.ULONG),
        ('Bytes', wintypes.ULONG),
        ('CompressedBytes', wintypes.ULONG),
        ('CompressFlushes', wintypes.ULONG),
        ('Errors', wintypes.ULONG),
        ('Timeouts', wintypes.ULONG),
        ('AsyncFramingError', wintypes.ULONG),
        ('AsyncOverrunError', wintypes.ULONG),
        ('AsyncOverflowError', wintypes.ULONG),
        ('AsyncParityError', wintypes.ULONG),
        ('TdErrors', wintypes.ULONG),
        ('ProtocolType', wintypes.USHORT),
        ('Length', wintypes.USHORT),
        ('Specific', SPECIFIC),
    )


class THINWIRECACHE (ctypes.Structure):
    '''
        ThinWireCore Cache
    '''
    __slots__ = ()
    _fields_ = (
        ('CacheReads', wintypes.ULONG),
        ('CacheHits', wintypes.ULONG),
    )


class RESERVED_CACHE(ctypes.Structure):
    '''
        Reserved Cache
    '''
    __slots__ = ()
    _fields_ = (
        ('ThinWireCache[', THINWIRECACHE * MAX_THINWIRECACHE),
    )


class CACHE_STATISTICS(ctypes.Structure):
    '''
        Cache Statistics
    '''
    __slots__ = ()
    class SPECIFIC(ctypes.Union):
        '''
            Cache Statistics Specific
        '''
        __slots__ = ()
        _fields_ = (
            ('ReservedCacheStats', RESERVED_CACHE),
            ('TShareCacheStats', wintypes.ULONG),
            ('Reserved', wintypes.ULONG * 20),
        )
    _fields_ = (
        ('ProtocolType', wintypes.USHORT),
        ('Length', wintypes.USHORT),
        ('Specific', SPECIFIC),
    )


class PROTOCOLSTATUS(ctypes.Structure):
    '''
        Protocol Status
    '''
    __slots__ = ()
    _fields_ = (
        ('Output', PROTOCOLCOUNTERS),
        ('Input', PROTOCOLCOUNTERS),
        ('Cache', CACHE_STATISTICS),
        ('AsyncSignal', wintypes.ULONG),
        ('AsyncSignalMask', wintypes.ULONG),
    )


class WINSTATIONINFORMATION(ctypes.Structure):
    '''
        WinstationInformation
    '''
    __slots__ = ()
    _fields_ = (
        ('ConnectState', ctypes.c_long),
        ('WinStationName', wintypes.WCHAR * (WINSTATIONNAME_LENGTH + 1)),
        ('LogonId', wintypes.ULONG),
        ('ConnectTime', wintypes.LARGE_INTEGER),
        ('DisconnectTime', wintypes.LARGE_INTEGER),
        ('LastInputTime', wintypes.LARGE_INTEGER),
        ('LogonTime', wintypes.LARGE_INTEGER),
        ('Status', PROTOCOLSTATUS),
        ('Domain', wintypes.WCHAR * (DOMAIN_LENGTH + 1)),
        ('UserName', wintypes.WCHAR * (USERNAME_LENGTH + 1)),
        ('CurrentTime', wintypes.LARGE_INTEGER)
    )


winsta.WinStationQueryInformationW.restype = wintypes.BOOLEAN

winsta.WinStationQueryInformationW.argtypes = (
    wintypes.HANDLE, # ServerHandle
    wintypes.ULONG,  # SessionId
    ctypes.c_long,   # WinStationInformationClass
    wintypes.LPVOID, # pWinStationInformation
    wintypes.ULONG,  # WinStationInformationLength
    wintypes.PULONG, # pReturnLength
)


def get_wts_session_info(session_id=LOGONID_CURRENT,
                  server_handle=SERVERNAME_CURRENT):
    '''
        Get Idle Time from Windows unsupported function courtesy of Eryk Sun <eryksun@gmail.com>
    '''
    info = WINSTATIONINFORMATION()
    rlen = wintypes.ULONG()
    if not winsta.WinStationQueryInformationW(
                server_handle, session_id, WinStationInformation,
                ctypes.byref(info), ctypes.sizeof(info), ctypes.byref(rlen)):
        raise ctypes.WinError(ctypes.get_last_error())
    return info


# https://stackoverflow.com/questions/61691557/python-ctypes-enumerate-sessionids
class WTS_SESSION_INFOW(ctypes.Structure):
    '''
        DocString
    '''
    _fields_ = [("SessionId", ctypes.c_ulong),
                ("pWinStationName", ctypes.c_wchar_p),
                ("State", ctypes.c_int)]

# you are supposedly able to enumerate sessions from remote systems, but in my testing, it did not work
# wts_handle = ctypes.windll.wtsapi32.WTSOpenServerW(b'some-server-name')

ppSessionInfo = ctypes.POINTER(WTS_SESSION_INFOW)()
pCount = ctypes.c_ulong()
# NOTE: the wts_handle doesnt seem to work, but the local server does
#     ctypes.windll.wtsapi32.WTSEnumerateSessionsW(wts_handle, 0, 1, ctypes.byref(ppSessionInfo), ctypes.byref(pCount))
ctypes.windll.wtsapi32.WTSEnumerateSessionsW(0, 0, 1, ctypes.byref(ppSessionInfo), ctypes.byref(pCount))

for index in range(pCount.value):
    if ppSessionInfo[index].pWinStationName == "Services" or ppSessionInfo[index].SessionId in  [1, 65536]:
        # not real RDP sessions by actual users
        continue
    print(f'Session ID: {ppSessionInfo[index].SessionId}')

    session_info = get_wts_session_info(ppSessionInfo[index].SessionId)

    # NOTE: this doesn't match up 100% with what Server Manager displays for connect, idle time, etc, but its close enough for me
    if session_info.ConnectState == WINSTATIONSTATECLASS.Disconnected.value:
        last_input_time =  get_datetime_from_windows_epoch(session_info.DisconnectTime)
    elif session_info.ConnectState == WINSTATIONSTATECLASS.Active.value:
        last_input_time = get_datetime_from_windows_epoch(session_info.CurrentTime)
    else:
        last_input_time =  get_datetime_from_windows_epoch(session_info.LastInputTime)
    print(f'    {session_info.Domain}\\{session_info.UserName}')
    current_time = get_datetime_from_windows_epoch(session_info.CurrentTime)
    print(f'        Idle Time: {(current_time - last_input_time)}')
    print(f'        state: {WINSTATIONSTATECLASS(ppSessionInfo[index].State).name}')
    print(f'        WinStationName: {ppSessionInfo[index].pWinStationName}')
