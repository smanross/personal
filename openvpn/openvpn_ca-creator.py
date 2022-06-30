'''
    Original scripting for this came from: https://gist.github.com/Justasic/908ef5f4fa162f15b3b8

    Given the maintainer of the OpenSSL library suggests usage of cryptography instead, I chose to rewrite it using cryptography.

    Create CA and Server/Client Certificates for OpenVPN on DD-WRT routers

    Tested with:
        Python 3.9.12 (x64)
        pip module: cryptography==37.0.2

        DD-WRT for Netgear R7000 (r49081 - 2022-06-04):
             https://dd-wrt.com/support/other-downloads/?path=betas%2F2022%2F06-04-2022-r49081%2Fnetgear-r7000%2F

             Note this thread because Netgear started blocking firmware downgrades (like DD-WRT typically does in its firmware "upgrade" to BASE DD-WRT flash):
                 https://wiki.dd-wrt.com/wiki/index.php/Netgear_R7000#How_to_install.
                    See "Flash from OEM" section that refers to Netgear firmware 1.0.9.64_10.2.64 and newer firmwares)
                      * I did not use the TFTP installation method

    This script will maintain a list of the certificates issued, the serial numbers of the certs, CA Keys and CA Certificates, and generate
        the .ovpn file for use in connecting to OpenVPN while using most of the same functions the original author of this script created
        (while I modified it for using the "cryptography" package).

        * in essence this script can act like a CA in a limited fashion
           (but is far from complete, because it doesn't handle CRLs, or anything more than code_signing, server_auth and client_auth certificates)
           the certificates issued by this script have been tested using a DD-WRT Router (a NetGear R7000), using the DD-WRT OpenVPN guide as a reference for setup.
               Sign up on the DD-WRT forum (http://www.dd-wrt.com) for access to the OpenVPN configuratuon guide document.

           There is nothing stopping you from using this to create OpenVPN CA, Server and Client auth certificates
                (with non-DD-WRT OpenVPN solutions -- nothing here is customized for the DD-WRT implementation).

    Updated most of the references in the original script to PY3 compatability, and dropped compatability for PY2, sorry if that's important to you.
'''
import os
from os.path import exists
import datetime
import configparser
from cryptography.hazmat.backends.openssl.rsa import _RSAPrivateKey as RSAPrivateKey

import cryptography
from cryptography import x509

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

cfg = configparser.ConfigParser()
if exists('openvpn_ca-creator.ini'):
    cfg.read('openvpn_ca-creator.ini')
    # get your preferred path to store all the CA, cert and .ovpn files
    BASE_PATH = cfg['general']['BASE_PATH']
else:
    # using expandvars to be able to embed environment variables in path
    BASE_PATH = os.path.expandvars("%USERPROFILE%\\Documents\\Customers")

# ExtendedKeyUsage
EKU = {
    'server_auth': x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
    'client_auth': x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
    'code_signing': x509.oid.ExtendedKeyUsageOID.CODE_SIGNING,
}

# Modified https://gist.github.com/Justasic/908ef5f4fa162f15b3b8
#   in order to start using "cryptography" module instead of the OpenSSL library, as the OpenSSL author suggests it shouldn't be used in favor of cryptography
# Kudos to these articles that helped me when I went astray
#     https://stackoverflow.com/questions/56285000/python-cryptography-create-a-certificate-signed-by-an-existing-ca-and-export
#     https://stackoverflow.com/questions/23103878/sign-csr-from-client-using-ca-root-certificate-in-python
#     https://github.com/pyca/cryptography/issues/4272
#     https://gist.github.com/major/8ac9f98ae8b07f46b208

def make_key(key_size=2048):
    '''
        Make an RSA key
    '''
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend()
    )
    return key


def make_csr(priv_key, CN, C=None, ST=None, L=None, O=None, OU=None, sans:list=None, password=None, extendedKeyUsage=None, hash_algorithm=hashes.SHA256()):
    '''
        Create a CSR using cryptography
    '''

    csr = x509.CertificateSigningRequestBuilder()

    subject_names = create_subject_names(CN, C, ST, L, O, OU, email='')

    csr = csr.subject_name(
            x509.Name(subject_names)
        )

    csr = csr.add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True,
        )
    if extendedKeyUsage and extendedKeyUsage in EKU:
        csr = csr.add_extension(
                x509.ExtendedKeyUsage([EKU[extendedKeyUsage]]), critical=True
            )

    if password:
        # will not typically use a password for openvpn
        csr = csr.add_attribute(
            x509.oid.AttributeOID.CHALLENGE_PASSWORD, password
        )

    # sans not tested but left in in case its important to you
    if sans and isinstance(sans, list):
        dns_name_list = []
        for san in sans:
            dns_name_list.append(x509.DNSName(san))

        csr = csr.add_extension(x509.SubjectAlternativeName(dns_name_list),
                                critical=False)

    request = csr.sign(priv_key, hash_algorithm)

    return request


def create_subject_names(CN, C, ST, L, O, OU, email):
    '''
        create the subject_names list for the appropriate certificate functions
    '''
    subject_names = [x509.NameAttribute(cryptography.x509.oid.NameOID.COMMON_NAME, CN)]

    if O:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.ORGANIZATION_NAME, O))
    if C:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.COUNTRY_NAME, C))
    if ST:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.STATE_OR_PROVINCE_NAME, ST))
    if L:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.LOCALITY_NAME, L))
    if OU:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.ORGANIZATIONAL_UNIT_NAME, ST))
    if email:
        subject_names.append(x509.NameAttribute(cryptography.x509.oid.NameOID.EMAIL_ADDRESS, email))

    return subject_names


def create_ca(CN, C="", ST="", L="", O="", OU="", valid_days=3650 * 2, key_size=2048, hash_algorithm=hashes.SHA256()):
    '''
        Create a CA Certificate (20 year validaty by default -- give or take a few leap days)
    '''

    root_key = make_key(key_size)

    subject_names = create_subject_names(CN, C, ST, L, O, OU, email='')
    ca_subject = x509.Name(subject_names)

    root_cert = x509.CertificateBuilder()

    root_cert = root_cert.subject_name(ca_subject)\
        .issuer_name(ca_subject)\
        .public_key(root_key.public_key())\
        .serial_number(1)\
        .not_valid_before(datetime.datetime.utcnow())\
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=valid_days))

    root_cert = root_cert.add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    )

    root_cert = root_cert.sign(root_key, hash_algorithm, default_backend())

    return (root_cert, root_key)

def create_certificate_from_csr(csr, root_key, serial, root_cert, valid_days=3650 * 2):
    '''
        Create a certificate from CA cert (20 year validity by default -- give or take a few leap days)
    '''
    cert = x509.CertificateBuilder().subject_name(csr.subject
        ).issuer_name(
            root_cert.subject
        ).public_key(
            csr.public_key()
        ).serial_number(
            serial
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=valid_days)
        )

    for ext in csr.extensions:
        cert = cert.add_extension(
            ext.value, ext.critical
        )

    cert = cert.sign(root_key, csr.signature_hash_algorithm)
        # return certificate
    return cert


# Dumps content to a string
def dump_file_in_mem(material, file_format=serialization.Encoding.PEM):
    '''
        Dump a Cert file in a specific file format

        This handles the basics, but needs work if you want to dump in a format like DER (and not PEM)
    '''

    data = None
    if isinstance(material, cryptography.x509.base.Certificate) or \
       isinstance(material, cryptography.x509.base.CertificateSigningRequest):
        data = material.public_bytes(file_format)
    elif isinstance(material, RSAPrivateKey):
        data = material.private_bytes(file_format,
                                      format=serialization.PrivateFormat.PKCS8,
                                      encryption_algorithm=serialization.NoEncryption())
    else:
        raise Exception(f"Don't know how to dump content type to file: {type(material)} ({material})")

    return data


def load_from_file(materialfile, objtype, file_format=serialization.Encoding.PEM):
    '''
        Load a file from a specific file format
    '''
    load_func = None
    if file_format == serialization.Encoding.PEM:
        if objtype == "Certificate":
            load_func = x509.load_pem_x509_certificate
        elif objtype == "CertificateSigningRequest":
            load_func = x509.load_pem_x509_csr
        elif objtype == "RSAPrivateKey":
            load_func = serialization.load_pem_private_key
    else:
        raise Exception(f"Unsupported material type: {objtype} - file_format: {file_format}")

    with open(materialfile, 'r') as fp:
        buf = fp.read()
    if objtype == "RSAPrivateKey":
        material = load_func(buf.encode('utf-8'), password=None)
    else:
        material = load_func(buf.encode('utf-8'))
    return material

def retrieve_key_from_file(keyfile):
    '''
        Get a key from the file
    '''
    return load_from_file(keyfile, "RSAPrivateKey")

def retrieve_csr_from_file(csrfile):
    '''
        Get a csr from a file
    '''
    return load_from_file(csrfile, "CertificateSigningRequest")

def retrieve_cert_from_file(certfile):
    '''
        Get a cert from a file
    '''
    return load_from_file(certfile, "Certificate")

def dump_string_to_file(strng, file, write_mode = 'x'):
    '''
        dump a cert/string to a file
    '''
    with open(file, write_mode) as f:
        f.write(strng)
        f.close()
    return True

def get_next_serial(filename):
    '''
        Get the next serial number
    '''
    if not exists(filename):
        # the CA would be serial 1 and the file doesnt exist, so its likely that its never issued a certificate
        with open(filename,'x') as f:
            f.write('[ca]\nlast_used_serial_number=2')
        return 2
    else:
        config = configparser.ConfigParser()
        config.read(filename)
        next_serial = int(config['ca']['last_used_serial_number']) + 1
        config['ca']['last_used_serial_number'] = str(next_serial)
        with open(filename, 'w') as f:
            config.write(f, space_around_delimiters=False)
        return next_serial

def make_new_ovpn_file(cust_name, cert_name, ca_cert='ca.crt', ca_key='ca.key', commonoptspath='commonopts.txt', extendedKeyUsage='server_auth', key_size=2048):
    '''
        build an ovpn file from the key material
    '''
    # Read our common options file first

    base_dir = f'{BASE_PATH}\\{cust_name}\\openvpn'

    # commonoptsfile has extra stuff you want added to your .ovpn file
    commonoptsfile = f'{base_dir}\\{commonoptspath}'
    if exists(commonoptsfile):
        f = open(commonoptsfile, 'r')
        common = f.read()
        f.close()
    else:
        common = ""

    cafile = f'{base_dir}\\{ca_cert}'
    cakeyfile = f'{base_dir}\\{ca_key}'

    if exists(cafile) and exists(cakeyfile):
        cakey  = retrieve_key_from_file(cakeyfile)
        cacert = retrieve_cert_from_file(cafile)
    else:
        (cacert, cakey) = create_ca(CN=f'{cust_name.capitalize()} CA')
        dump_string_to_file(dump_file_in_mem(cacert).decode('utf-8'), cafile)
        dump_string_to_file(dump_file_in_mem(cakey).decode('utf-8'), cakeyfile)
        if not exists(f'{base_dir}\\certs'):
            os.makedirs(f'{base_dir}\\certs')

    # Generate a new private key pair for a new certificate.
    key = make_key(key_size)
    # Generate a certificate request
    csr = make_csr(key, cert_name, extendedKeyUsage=extendedKeyUsage)
    serial = get_next_serial(f'{base_dir}\\serials.ini')
    # Sign the certificate with the new csr
    crt = create_certificate_from_csr(csr, cakey, serial, cacert)
    print(f'created certificate with serial: {serial} and subject: {cert_name}')
    # Now we have a successfully signed certificate. We must now
    # create a .ovpn file and then dump it somewhere.
    clientkey  = dump_file_in_mem(key).decode('utf-8')
    clientcert = dump_file_in_mem(crt).decode('utf-8')
    cacertdump = dump_file_in_mem(cacert).decode('utf-8')
    ovpn = f"{common}<ca>\n{cacertdump}</ca>\n<cert>\n{clientcert}</cert>\n<key>\n{clientkey}</key>\n"

    certfile = f'{base_dir}\\certs\\{serial}-{cert_name}.crt'
    dump_string_to_file(clientcert, certfile)
    dump_string_to_file(ovpn, f'{base_dir}\\{cust_name}-{cert_name}.ovpn', write_mode = 'w')

if __name__ == "__main__":
     # while you dont need the "server" .ovpn file, this will create a server certificate (and the CA if needed, or use the existing CA cert and key)
    make_new_ovpn_file("somecustomer", cert_name='server')
    make_new_ovpn_file("somecustomer", cert_name='client', extendedKeyUsage=b'client_auth')
    print("Done")
