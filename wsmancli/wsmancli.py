"""
    This code is trying to emulate the wsman client EXE:
        winrm get winrm/config/listener?Address=*+Transport=HTTPS
        winrm enum winrm/config/listener
        winrm create winrm/config/listener?Address=*+Transport=HTTPS @{HostName="somefddn";CertificateThumbprint="somethumbprint"}
        winrm delete winrm/config/listener?Address=*+Transport=HTTPS @{HostName="somefqdn";CertificateThumbprint="somethumbprint"}

    Kudos to Justin Borean for his work on the pypsrp module, and the wsman submodule that this is based off of

    prerequisites:
        pip install pypsrp
"""

from pypsrp.wsman import WSMan, NAMESPACES, SelectorSet
import xmltodict
import json
import xml.etree.ElementTree as ET


class WSManClient(object):
    def __init__(self, hostname, username=None, password=None, ssl=True, auth="negotiate", encryption="always", cert_validation=True):
        self.wsman = WSMan(server=hostname, username=username, password=password, ssl=ssl, auth=auth, encryption=encryption, cert_validation=cert_validation)

    def get(self, transport="HTTPS", address="*"):
        selector_set = SelectorSet()
        selector_set.add_option("Transport", transport)
        selector_set.add_option("Address", address)

        element = self.wsman.get(resource_uri="http://schemas.microsoft.com/wbem/wsman/1/config/listener", resource=None, selector_set=selector_set)

        myjson = self._create_json_from_xml(element)

        results = self._parse_objects(myjson["s:Body"]["ns1:Listener"])

        return results

    # enumerate
    def enumerate(self, max_elements: str = "2000"):
        # generates additional XML to the payload in the body in order to get the enumerate to work:
        #   '<s:Body><wsen:Enumerate><wsman:OptimizeEnumeration/><wsman:MaxElements>2000</wsman:MaxElements> </wsen:Enumerate></s:Body>'

        enum = self._create_element(NAMESPACES["wsen"], "Enumerate")
        optimize = self._create_element(NAMESPACES["wsman"], "OptimizeEnumeration")

        max_elem = self._create_element(NAMESPACES["wsman"], "MaxElements")
        max_elem.text = max_elements

        # insert the optimize and max_elements inside the <wsen:Enumerate />
        enum.append(optimize)
        enum.append(max_elem)

        element = self.wsman.enumerate(resource_uri="http://schemas.microsoft.com/wbem/wsman/1/config/listener", resource=enum)

        myjson = self._create_json_from_xml(element)
        results = self._parse_objects(myjson["s:Body"]["wsen:EnumerateResponse"]["wsman:Items"]["ns3:Listener"])

        return results

    def create(self, hostname, certificate_thumbprint, transport="HTTPS", address="*"):
        # really only tested this on HTTPS
        https_selector_set = SelectorSet()
        https_selector_set.add_option("Transport", transport)
        https_selector_set.add_option("Address", address)

        resource = self._create_element(NAMESPACES["wsman"], "Listener")

        host_name = self._create_element(NAMESPACES["wsman"], "HostName")
        host_name.text = hostname

        resource.append(host_name)

        if transport == "HTTPS":
            # if it's for http, then tere would be no thumbprint
            cert_thumbprint = self._create_element(NAMESPACES["wsman"], "CertificateThumbprint")
            cert_thumbprint.text = certificate_thumbprint
            resource.append(cert_thumbprint)

        element = self.wsman.create(resource_uri="http://schemas.microsoft.com/wbem/wsman/1/config/listener", resource=resource, selector_set=https_selector_set)

        # as long as there's no exception, the create worked
        return element

    def delete(self, transport, hostname, certificate_thumbprint, address="*"):
        # really only tested this on HTTPS
        https_selector_set = SelectorSet()
        https_selector_set.add_option("Transport", transport)
        https_selector_set.add_option("Address", address)

        resource = self._create_element(NAMESPACES["wsman"], "Listener")

        host_name = self._create_element(NAMESPACES["wsman"], "HostName")
        host_name.text = hostname

        cert_thumbprint = self._create_element(NAMESPACES["wsman"], "CertificateThumbprint")
        cert_thumbprint.text = certificate_thumbprint

        resource.append(host_name)
        resource.append(cert_thumbprint)

        element = self.wsman.delete(resource_uri="http://schemas.microsoft.com/wbem/wsman/1/config/listener", resource=resource, selector_set=https_selector_set)

        # as long as there's no exception, the delete worked

        return element

    # this is left over for sets/puts -- havent debugged this yet
    """
    def set(self, transport, hostname, certificate_thumbprint, address="*"):
        https_selector_set = SelectorSet()
        https_selector_set.add_option("Transport", transport)
        https_selector_set.add_option("Address", address)

        resource = ET.Element("{%s}%s" % (NAMESPACES["wsman"], "Listener"))

        host_name = ET.Element("{%s}%s" % (NAMESPACES["wsman"], "HostName"))
        host_name.text = hostname

        cert_thumbprint = ET.Element("{%s}%s" % (NAMESPACES["wsman"], "CertificateThumbprint"))
        cert_thumbprint.text = certificate_thumbprint

        resource.append(host_name)
        resource.append(cert_thumbprint)

        # not sure about this
        element = wsman._invoke(WSManAction.PUT, resource_uri="http://schemas.microsoft.com/wbem/wsman/1/config/listener", resource=resource, selector_set= https_selector_set)
    """

    def _parse_objects(self, objects: list, debug=False):
        """
            get rid of the xml node names and leave it with the valuable parts of the names in the data

            gotta validate this works all over, but it does for the listeners :)
        """
        if debug:
            print(objects)

        if isinstance(objects, dict):
            objects = [objects]

        _objects = []
        for object in objects:
            obj = {}
            for key, item in object.items():
                obj[key.split(":")[1]] = item
            _objects.append(obj)
        return _objects

    def _create_element(self, namespace_entry, value):
        element = ET.Element("{%s}%s" % (namespace_entry, value))

        return element

    def _create_json_from_xml(self, xml_element):
        xml_string = ET.tostring(xml_element, encoding="utf8").decode("utf8")
        obj = xmltodict.parse(xml_string)
        myjson = json.loads(json.dumps(obj))

        return myjson


if __name__ == "__main__":

    # first, lets just negotiate the credentials from the currently logged in user
    wsman = WSManClient(
        "someserver.somedomain.local",
        ssl=False,  # set to false so that if the HTTPS listener is not setup or getting deleted, this will still succeed
        # negotiate tries to use the locally logged in uer creds for the authentication,  (tested)
        # change to ntlm and send username/password parameters if you need to log in as someoen else (tested)
        auth="negotiate",
        encryption="always",
        cert_validation=False)

    # enumerate all of the listeners
    wsman.enumerate()
    # get the HTTP Listener
    wsman.get("HTTP", "*")
    # get the HTTPS Listener
    wsman.get("HTTPS", "*")

    # now lets just use username/password
    import getpass

    password = getpass.getpass(prompt="Password for user: ", stream=None)

    # this will work remotely if the appropriate firewall rules are configured to allow it
    wsman = WSManClient(
        "someserver.somedomain.local",
        ssl=False,  # set to false so that if the HTTPS listener is not setup or getting deleted, this will still succeed
        auth="ntlm",
        encryption="always",
        username="someuser@somedomain.local",
        password=password,
        cert_validation=False)

    # enumerate all of the listeners
    wsman.enumerate()
    # get the HTTP Listener
    wsman.get("HTTP", "*")
    # get the HTTPS Listener
    wsman.get("HTTPS", "*")

    # the thumbprint below is a sha1 digest of the certificate fingerprint
    # https://www.mail-archive.com/cryptography-dev@python.org/msg00503.html
    # in the python cryptography module, you would use this to get the thumbprint from the x509 certificate
    # thumbprint = cert.fingerprint(hashes.SHA1()).hex()

    # create an HTTPS mapping with the defined cert
    # wsman.create(transport="HTTPS", address="*", hostname="someserver.somedomain.local", certificate_thumbprint="somethumbprint")
    # delete an HTTPS mapping
    # wsman.delete(transport="HTTPS", address="*", hostname="someserver.somedomain.local", certificate_thumbprint="somethumbprint")
    # create HTTPS mapping again so it will be available again
    # wsman.create(transport="HTTPS", address="*", hostname="someserver.somedomain.local", certificate_thumbprint="somethumbprint")
