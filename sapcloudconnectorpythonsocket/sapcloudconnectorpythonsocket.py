"""
CloudConnectorSocket instance of Pythons socket class overriding the connect function to open a socket via SAP Cloud Connector.
"""
import functools
import socket
import struct
import base64
import logging

logger = logging.getLogger('sapcloudconnectorpythonsocket')
logger.addHandler(logging.NullHandler())


def format_status_byte(status_byte) -> str:
    """helper function to log the CC specific error bytes"""
    status_byte_messages = {
        b"\x00": "SUCCESS: Success",
        b"\x01": "FAILURE: Connection closed by backend or general scenario failure.",
        b"\x02": "FORBIDDEN: Connection not allowed by ruleset. No matching host mapping found in Cloud Connector access control settings, see Configure Access Control (TCP).",
        b"\x03": "NETWORK_UNREACHABLE: The Cloud Connector is not connected to the subaccount and the Cloud Connector Location ID that is used by the cloud application can't be identified. See Connect and Disconnect a Cloud Subaccount and Managing Subaccounts, section Procedure.",
        b"\x04": "HOST_UNREACHABLE: Cannot open connection to the backend, that is, the host is unreachable.",
        b"\x05": "CONNECTION_REFUSED: Authentication failure",
        b"\x06": "TTL_EXPIRED: Not used",
        b"\x07": "COMMAND_UNSUPPORTED: Only the SOCKS5 CONNECT command is supported.",
        b"\x08": "ADDRESS_UNSUPPORTED: Only the SOCKS5 DOMAIN and IPv4 commands are supported."
    }
    return status_byte_messages[status_byte] if status_byte in status_byte_messages else "Other Unexpected Error byte"

def set_self_blocking(function):
    """helper to use blocking on socket object"""
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        self = args[0]
        try:
            _is_blocking = self.gettimeout()
            if _is_blocking == 0:
                self.setblocking(True)
            return function(*args, **kwargs)
        except Exception as e:
            raise e
        finally:
            if _is_blocking == 0:
                self.setblocking(False)
    return wrapper



class CloudConnectorSocket(socket.socket):
    """Cloud Connector socket based on SOCKS5 standard"""

    def __init__(self, family=socket.AF_INET, type=socket.SOCK_STREAM, proto=0, *args, **kwargs):
        """set default params for TCP socket"""
        super(CloudConnectorSocket, self).__init__(family, type, proto, *args, **kwargs)
    
    timeout = 30 # default

    @set_self_blocking
    def connect(self, dest_host: str, dest_port: int, proxy_host: str, proxy_port: int, token: str, location_id: str=None):
        """
        Connect to the destination host via the proxy host

        :param dest_host: The host of the destination
        :param dest_port: The (int) port of the destination
        :param proxy_host: The host of the proxy
        :param proxy_port: The port of the proxy
        :param token: The token from the connectivity-service instance
        :param location_id: (Optional) specify the Cloud Connector location_id to connect to (if set in cloud connector config else leave empty)
        """
        super(CloudConnectorSocket, self).settimeout(self.timeout)
        
        try:
            # Initial connection to proxy server
            super(CloudConnectorSocket, self).connect((proxy_host, proxy_port))
        except Exception as e:
            self.close()
            raise Exception(f"EXCEPTION AT INITIAL CONNECT: {e}")
            
        
        try:                
            # Connected to proxy server, now negotiate authentication
            self.negotiate_auth(dest_host, dest_port, token, location_id)
        except Exception as e:
            self.close()
            raise Exception(f"EXCEPTION NEGOTIATIONG {e}")

                
    def negotiate_auth(self, dest_host, dest_port, token, location_id):
        """SAP Cloud Connector specific authentication scheme"""
        self.settimeout(None)   # apparently needed for make file to set to blocking https://stackoverflow.com/questions/3432102/python-socket-connection-timeout
        writer = self.makefile("wb")
        reader = self.makefile("rb", 0)  # buffering=0 renamed in Python 3
        try:
            # 5 is for command, 1 for length of auth list, 80 is custom auth type of cc
            writer.write(b"\x05\x01\x80")
            writer.flush()

            chosen_auth = self.readAll(reader, 2)
            logger.info(f"Chosen Auth Status: {chosen_auth[0:1]} Success: {chosen_auth[1:2]}")

            if chosen_auth[0:1] != b"\x05":
                raise Exception("SOCKS5 PROXY SERVER SENT UNEXPECTED DATA FOR CHOSE AUTH")

            # Check if 80 method is confirmed

            if chosen_auth[1:2] == b"\x80":
                location_id_part = b"\x00"
                if location_id:
                    encoded_location_id = base64.b64encode(location_id.encode())
                    location_id_part = len(encoded_location_id).to_bytes(1, byteorder="big") + encoded_location_id
                auth_message = b"\x01" + len(token.encode()).to_bytes(4, byteorder="big") + token.encode() + location_id_part
                logger.info(auth_message)
                writer.write(auth_message)
                writer.flush()

                auth_status = self.readAll(reader, 2)
                logger.info(f"Auth Status: {auth_status[0:1]} Success: {auth_status[1:2]}")
           
                
                if auth_status[0:1] != b"\x01":
                    raise Exception("CLOUD CONNECTOR SENT UNEXPECTED DATA FOR AUTH")
                if auth_status[1:2] != b"\x00":
                    # Authentication failed
                    raise Exception("SOCKS5 AUTH FAILED " + format_status_byte(auth_status[1:2]))
            
            else:
                raise Exception("CLOUD CONNECTOR SENT UNEXPECTED CHOSEN AUTH TYPE NOT x80")    
                
            # authentication succeeded and can request actual connection
            # x05 start of message x01 command x00 standard end of command

            writer.write(b"\x05\x01\x00")
            resolved = self.writeSOCKS5address(dest_host, dest_port, writer)
            logger.info("flush")
            writer.flush()

            # Get the response
            resp = self.readAll(reader, 3)
            logger.info(f"output of the command byte {resp[0:1]} {resp[1:2]} {resp[2:3]}")

            if resp[0:1] != b"\x05":
                raise Exception("SOCKS5 proxy server sent invalid data")

            status = resp[1:2]
            logger.info(f"STATUS AFTER COMMAND {status}")

            if status != b"\x00":
                # Connection failed: server returned an error
                raise Exception("STATUS ERROR AFTER COMMAND BYTE " + format_status_byte(status))

            # Get the bound address/port
            bnd = self.readSOCKS5address(reader)
            logger.info((resolved, bnd))
            super(CloudConnectorSocket, self).settimeout(self.timeout)
        finally:
            reader.close()
            writer.close()
            
            
    def readAll(self, file, count):
        """Receive EXACTLY the number of bytes requested from the file object.
        Blocks until the required number of bytes have been received."""
        data = b""
        while len(data) < count:
            d = file.read(count - len(data))
            if not d:
                raise Exception("ERROR IN READ ALL NOT ENOUGH BYTES TO READ -> MIGHT MEAN CONN AWAY")
            data += d
        return data
    
    
    def writeSOCKS5address(self, dest_host, dest_port, file):
        """
        Return the host and port packed for the SOCKS5 protocol,
        and the resolved address as a tuple object.
        """
        host, port = dest_host, dest_port
        rdns = True
        
        family_to_byte = {socket.AF_INET: b"\x01", socket.AF_INET6: b"\x04"}

        # If the given destination address is an IP address, we'll
        # use the IP address request even if remote resolving was specified.
        # Detect whether the address is IPv4/6 directly.
        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                addr_bytes = socket.inet_pton(family, host)
                file.write(family_to_byte[family] + addr_bytes)
                host = socket.inet_ntop(family, addr_bytes)
                file.write(struct.pack(">H", port))
                return host, port
            except socket.error:
                continue

        # Well it's not an IP number, so it's probably a DNS name.
        if rdns:
            # Resolve remotely
            host_bytes = host.encode("idna")
            file.write(b"\x03" + chr(len(host_bytes)).encode() + host_bytes)
        else:
            # Resolve locally
            addresses = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                           socket.SOCK_STREAM,
                                           socket.IPPROTO_TCP,
                                           socket.AI_ADDRCONFIG)
            # We can't really work out what IP is reachable, so just pick the
            # first.
            target_addr = addresses[0]
            family = target_addr[0]
            host = target_addr[4][0]

            addr_bytes = socket.inet_pton(family, host)
            file.write(family_to_byte[family] + addr_bytes)
            host = socket.inet_ntop(family, addr_bytes)
        file.write(struct.pack(">H", port))
        return host, port
    
    def readSOCKS5address(self, file):
        atyp = self.readAll(file, 1)
        if atyp == b"\x01":
            addr = socket.inet_ntoa(self.readAll(file, 4))
        elif atyp == b"\x03":
            length = self.readAll(file, 1)
            addr = self.readAll(file, ord(length))
        elif atyp == b"\x04":
            addr = socket.inet_ntop(socket.AF_INET6, self.readAll(file, 16))
        else:
            raise Exception("SOCKS5 proxy server sent invalid data at read adress")

        port = struct.unpack(">H", self.readAll(file, 2))[0]
        logger.info((addr, port))
        return addr, port
        
        
        