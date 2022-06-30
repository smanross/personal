'''
  Get new chrome driver version
'''
import os
import sys
import zipfile
import shutil
import requests
import win32api
from selenium import webdriver


def getFileProperties(fname):
    """
    Kudos:  https://stackoverflow.com/questions/580924/how-to-access-a-files-properties-on-windows
    Read all properties of the given file return them as a dictionary.
    """
    propNames = ('Comments', 'InternalName', 'ProductName',
                 'CompanyName', 'LegalCopyright', 'ProductVersion',
                 'FileDescription', 'LegalTrademarks', 'PrivateBuild',
                 'FileVersion', 'OriginalFilename', 'SpecialBuild')

    props = {'FixedFileInfo': None, 'StringFileInfo': None, 'FileVersion': None}

    try:
        # backslash as parm returns dictionary of numeric info corresponding to VS_FIXEDFILEINFO struc
        fixedInfo = win32api.GetFileVersionInfo(fname, '\\')
        props['FixedFileInfo'] = fixedInfo
        props['FileVersion'] = f"{int(fixedInfo['FileVersionMS'] / 65536)}.{int(fixedInfo['FileVersionMS'] % 65536)}.{int(fixedInfo['FileVersionLS'] / 65536)}.{int(fixedInfo['FileVersionLS'] % 65536)}"  # noqa: E501

        # \VarFileInfo\Translation returns list of available (language, codepage)
        # pairs that can be used to retreive string info. We are using only the first pair.
        lang, codepage = win32api.GetFileVersionInfo(fname, '\\VarFileInfo\\Translation')[0]

        # any other must be of the form \StringfileInfo\%04X%04X\parm_name, middle
        # two are language/codepage pair returned from above

        strInfo = {}
        for propName in propNames:
            # i might be oversimplifying it by just adding the 0 and may need to "pad"
            # the resulting number string if its 3 chars
            strInfoPath = f'\\StringFileInfo\\0{hex(lang)[2:].upper()}0{hex(codepage)[2:].upper()}\\{propName}'
            # print(f' strInfoPath = {strInfoPath}')
            strInfo[propName] = win32api.GetFileVersionInfo(fname, strInfoPath)

        props['StringFileInfo'] = strInfo
    except Exception:
        pass

    return props


# I tend to put the chromedriver in my python directory (C:\python39\chromedriver.exe)

# get the existing driver version by running chromedriver.exe -v and parsing the output
driver_version = os.popen(f"{sys.exec_prefix}\\chromedriver.exe -v").read().split(" ")[1]

# now find out what version of the chrome browser you are using by looking at the file properties of chrome.exe
file_ver = getFileProperties("C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe")['FileVersion']

ver_list_file = file_ver.split(".")

if file_ver and driver_version and driver_version.split(".")[0] != ver_list_file[0]:
    # check the version of the driver exe versus the chrome executable file verison (we only care about the
    #     major version (NNN) NNN.XXX.XXX.XXXX)

    print(f'not a match: file_ver = {file_ver} != driver_ver: {driver_version}')

    # download the "LATEST_RELEASE_NNN" file to find out what the latest chrome driver for version NNN is
    url = f'https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{ver_list_file[0]}'
    r = requests.get(url, allow_redirects=True)
    if r.status_code != 200:
        r.raise_for_status()

    new_driver_ver = r.content.decode('utf-8')
    # now that we know what the latest chrome driver version is for the version of chrome we have
    #    is, download the new chromedriver_win32.zip
    url = f'https://chromedriver.storage.googleapis.com/{new_driver_ver}/chromedriver_win32.zip'
    r = requests.get(url, allow_redirects=True)
    if r.status_code != 200:
        r.raise_for_status()

    zip_file = 'c:\\temp\\chromedriver_win32.zip'
    open(zip_file, 'wb').write(r.content)

    extract_dir = "c:\\temp\\selenium_temp"
    os.makedirs(extract_dir, exist_ok=True)

    # extract the exe from the zip
    with zipfile.ZipFile(zip_file, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)

    ver_file = f'{sys.exec_prefix}\\chromedriver_v{ver_list_file[0]}.exe'
    temp_file = f'{extract_dir}\\chromedriver.exe'
    # move it to your python path as chromedriver_vNNN.exe
    #    (as a backup in case you want or need the older chromedriver files)
    os.rename(temp_file, ver_file)
    # copy the ver_file to the actual chromedriver.exe (in the python directory) so you can use it for selenium
    shutil.copy(ver_file, f'{sys.exec_prefix}\\chromedriver.exe')
    # and remove the zip file you downloaded
    os.unlink(zip_file)
    print(f'Updated chrome driver to current version: {ver_list_file[0]}')
else:
    print(f'matched chrome driver version: v{file_ver.split(".")[0]} -- nothing to update')

# start using selenium in the same script...
options = webdriver.ChromeOptions()

# chrome 77 requires a new way of disabling the automation infobar
options.add_experimental_option("excludeSwitches", ['enable-automation', 'load-extension'])

# current version of chrome driver/chrome causes issues if run as the "SYSTEM" Account (or via task scheduler)..
#   disabling this feature fixes the issue.
#   this seemed to start with chromedriver 72 and 73
options.add_argument("--disable-features=VizDisplayCompositor")

# Create a web browser instance
browser = webdriver.Chrome(options=options)

# Do Selenium stuff here

# close the browser and quit the webdriver
browser.close()
browser.quit()
