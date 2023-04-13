# sapcloudconnectorpythonsocket
Python Socket to connect to the SAP Cloud Connector via Connectivity Service

The SAP BTP Connectivity Proxy allows to connect to on-prem systems. It can act as a SOCKS5 Proxy to establish TCP connections. 
Due to its custom authentication scheme one can not use standard SOCKS5 client libaries. For details on how to authenticate against the Connectivity Proxy see the official Documentation. https://help.sap.com/docs/connectivity/sap-btp-connectivity-cf/using-tcp-protocol-for-cloud-applications

##Sample Usage:
```python 
from sapcloudconnectorpythonsocket import CloudConnectorSocket

cc_socket = CloudConnectorSocket()
cc_socket.connect(
    dest_host="virtualhost", 
    dest_port=3333, 
    proxy_host="connectivity-proxy", 
    proxy_port=20003, 
    token="<token>",
    location_id="CLOUD_CONNECTOR_LOCATION_ID"
)
```
Opens a socket in python using the SAP Cloud Connector as proxy. The standard socket object from python can be used in a various applications. Often times useful in connectig to TCP based protocols using python packages. The location_id is optional.
The destination host and port are the virtualhost and virtualport configured in the Cloud Connector configuration.
The proxy_host and the proxy_port are the host and port of the BTP Cloud Foundry Connectivity Proxy. The token is the authentication token to the Connectivity Proxy. They can be obtained from the Credentials of an BTP Connectivity Service instance.

To open a TCP based connection the proxy_port needs to be the port to the socks5 proxy. This is usually 20004 in the connectivity service.



