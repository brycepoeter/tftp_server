# Trivial File Transfer Protocol (TFTP) Server 
### Lightweight Read/Write over UDP/IP 

This is a basic TFTP server following the protocol codified in 
[RFC1350](https://tools.ietf.org/html/rfc1350) for 
use with devices with limited memory capacity.  

It's hard to imagine now, but back in the day, storage constraints 
on small devices could be such that software – and the protocols it 
lays out – had to be pared down to fit on the device. As such, 
there needed to be a bare-bones file-transfer protocol, one that was 
as small as could reasonably work, for instances when complicated 
transfer protocols involving large files and many sub-behaviors 
would not work in the circumstances. Enter TFTP! 

#### Basic Overview of TFTP 

I recommend reading the RFC, which is the definitive source of TFTP 
protocols and operations. It's not too long, about 10 pages. I also 
highly recommend reviewing the [TCP/IP Guide to TFTP](http://www.tcpipguide.com/free/t_TrivialFileTransferProtocolTFTP.htm) put out by Charles M. Kozierok. 
Whatever questions you have after reviewing the RFC will likely be answered there.  

In essence, the TFTP server listens for a read/write request (RRQ/WRQ), 
and then depending on the action, sends either DATA datagrams or ACK datagrams, 
expecting the counterpart in exchange from the client. So if the client sends 
a RRQ, the server will be sending DATA and expecting ACKs. And vice versa. 

Note: I have used the word "packet" throughout the code, but please be aware that 
UDP sends datagrams, not packets. 

Once a DATA datagram is sent, an ACK with the same block number is expected. 
The next DATA will not be sent until the ACK for the previous piece has been received. 

For instance, if DATA 2 is received, ACK 2 is sent. If DATA 2 is received again, that means 
ACK 2 was not received by client. ACK 2 is re-transmitted. If DATA 3 is received, the ACK 2
retransmission was received. ACK 3 is sent, and DATA 4 is expected. And so forth until 
the transaction either times out or is completed.  

Data is sent in 512-byte increments with a 4-byte header. The first time a data field is 
less than 512 bytes is an indication that the transfer has been completed. 

#### Using this Server

This server takes two arguments from command line, the first being port number and 
the second being timeout in milliseconds. The port number is the port on which the 
server will listen for incoming transmissions. When a RRQ/WRQ comes in, the server 
will handle the RRQ/WRQ on a new port between 1024 and 65535 and continue listening 
for new requests on the port the user specified. The timeout is the time in milliseconds 
the server will wait for a response before retransmitting the last DATA/ACK it sent. 

Sample usage: 


$ python tftp_server.py (port) (timeout)  


You can test the server using a tftp client in Terminal. Sample command sequence: 


$ tftp  
tftp> connect (server IP) (server port)     
tftp> binary   
tftp> verbose  
tftp> get sample.txt destination.txt / put sample.txt  


#### Acknowledgements 

This project was completed as part of Dave Sahota's Networks Winter 2021 class 
in the MPCS at the University of Chicago. While the Python code here is all mine, it 
is underpinned by Dave's instruction, and he provided the resources linked
above and the specific commands for using the tftp command-line client. 

