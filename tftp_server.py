import socket 
import sys 
import random
import time 
import re
import os


MAX_SIZE = 512 

opcodes = {
    'read': 1,
    'write': 2, 
    'data': 3, 
    'ack': 4, 
    'error': 5
}

mode_strings = ['netascii', 'octet', 'mail']


def make_packet(opcode, block_num): 
    '''
    This function takes opcode and block number 
    as parameters and outputs a bytearray with the 
    appropriate header values. You can then cusomize 
    this bytearray by appending to it, for instance 
    when opcode = 'data' and you want to send a payload 
    with the packet header. 
    
    In the case of opcode = 'ack', sending the result of 
    make_packet('ack', block_num) is sufficient to follow TFTP. 
    '''
    pack = bytearray()
    pack.append(0)
    pack.append(opcodes[opcode])
    pack.append(0)
    pack.append(block_num)
    return pack


def extract_filepath(data): 
    '''
    Extracts file path from bytes data 
    First decodes bytes into utf-8 
    Then the regex searches for a match where 
        1) First char is a-z or A-Z 
        2) 0+ alphanumeric chars that are not . follow
        3) Then one . 
        4) Then at least one but possibly more chars a-z or A-Z 
    If there is more than one match, throw error,
    perhaps because more than one file name entered, 
    and if no match, throw different error
    '''
    data_str = data.decode('utf-8')
    file_path = re.findall(r'([a-zA-Z][\w^\.]*\.[a-zA-Z]+)', data_str) 
    if len(file_path) > 1: 
        raise ValueError('Please make sure only one file name is entered')
    elif len(file_path) == 0:
        raise ValueError('Did not recognize valid file name') 
    else:
        return file_path[0]    


def transmit(packet, socket, client, timeout): 
    '''
    This function acts as a timer for re-sending packets
    It sends the packet to the client using the socket, 
    and then while there's no response and current time 
    is less than retransmit time, it listens for a response. 

    If there is no response before retransmit time, it calls
    transmit again, which re-sends the message and re-sets the timer 

    If res received is has an ERROR opcode, 
    system exits 
    '''
    res = None 
    socket.sendto(packet, client)
    retransmit = time.time() + timeout 
    while res == None and time.time() < retransmit: 
        res, client = socket.recvfrom(MAX_SIZE + 4)
    if res == None: 
        transmit(packet, socket, client, timeout)
    else: 
        if res[3] == opcodes['error']: 
            sys.exit('Received ERROR response')
        return res, client    


def handle_WRQ(file_name, client, socket, timeout): 
    '''
    Function to handle incoming WRQs 

    Initializes empty array and empty set of ACKed packets 
    Then sends initial ACK 0 to indicate readiness 
    and listens for the first DATA packet to be received 

    Inside the main loop, the most recent incoming data packet 
    has its block number checked against previously ACKed packets. 
    If the number has been previously ACKed, server sends the ACK 
    again and waits for a response. This will continue until the 
    server receives a packet with an un-ACKed block number. 

    The server then finds the size of the data packet. If it is > 4, 
    i.e. it is more than just a header, the data from positions [4:]
    are appended to all_data. If the size of the packet is < 516, TFTP 
    says that data transmission has finished, and the server sends a 
    final ACK and closes the connection. 

    If data is 516 bytes, however, the transaction continues. An ACK 
    is sent for the packet, the packet block number is added to the set 
    of ACKed packets, and the server listens for a response. Once a response 
    comes through, it is checked against packs_acked as above, and the 
    process repeats until a packet of size < 516 bytes is received and ACKed 

    Once all data has been transmitted, handle_WRQ then writes all_data 
    to a file with the same name as the one the client transferred 

    Finally, the socket is closed. 
    '''

    all_data = []
    packs_acked = set()

    res = make_packet('ack', 0)
    socket.sendto(res, client)
    print('Sent ACK 0')

    data, client = socket.recvfrom(MAX_SIZE + 4)
    print(f'Received DATA {data[3]}')


    while True:

        while data[3] in packs_acked: 
            print(f'Sent ACK {data[3]}') 
            data, client = transmit(make_packet('ack', data[3]), socket, client, timeout)
            print(f'Received DATA {data[3]}')
        if sys.getsizeof(data) > 4: 
            all_data.append(data[4:])
        if sys.getsizeof(data) < 516: 
            socket.sendto(make_packet('ack', data[3]), client)
            packs_acked.add(data[3]) 
            print(f'Sent ACK {data[3]} (Final ACK)')  
            break   
        packs_acked.add(data[3])  
        print(f'Sent ACK {data[3]}')       
        data, client = transmit(make_packet('ack', data[3]), socket, client, timeout)
        print(f'Received DATA {data[3]}')


    with open(file_name, 'w') as f: 
        file_text = ''
        for item in all_data: 
            item_str = item.decode('utf-8')
            file_text += item_str
        f.write(file_text)


    socket.close()
    print('Connection Closed')

    return


def handle_RRQ(file_path, client, socket, timeout): 
    '''
    This function tries to open file_path, and if 
    it succeeds, saves its content as doc. Doc is then 
    converted into bytes and split into 512-byte segments, 
    each of which is given the required 4-byte TFTP header
    for a total packet size of 516 bytes 

    These packets are added into a queue and then in turn
    sent to the client while 
        1) Neither server nor client has timed out 
        2) The # of ACKed packets < # total packets 

    After transmitting a packet, if a response is not 
    received within timeout number of seconds, the packet
    will be sent again 

    Each packet is sent in order, and each subsequent packet is 
    only sent once an ACK has been received for the preceding packet 

    If all packets are sent and ACKed with no error, 
    a success message is printed and the socket is closed. 

    Else, an error is raised and the socket is closed. 
    '''
    try: 
        with open(file_path, 'rb') as f: 
            doc = f.read()
    except: 
        raise ValueError('Could not find file')        
    

    doc_bytes = bytearray(doc)
    num_packets = len(doc_bytes) // 512 + 1
    packets = [x for x in range(num_packets)]
    for i in range(num_packets): 
        packet = make_packet('data', i + 1)
        packet += bytearray(doc_bytes[:512])
        packets[i] = packet
        doc_bytes = doc_bytes[512:]

    # if total data bytes divisible by 512, must send final packet with data size 0
    doc_mod = len(doc_bytes) % 512
    if doc_mod == 0:  
        packet = make_packet('data', len(packets))
        packets.append(packet)


    iter_pack = iter(packets)
    packs_acked = set()
    while len(packs_acked) < num_packets: 
        packet = next(iter_pack, packet)
        pack_acked = packet[3] in packs_acked  
        while pack_acked == False:  
            res, client = transmit(packet, socket, client, timeout)
            print(f'Sent DATA {packet[3]}')
            while res[3] != packet[3]: 
                res, client = transmit(packet, socket, client, timeout)
                print(f'Re-sent DATA {packet[3]}')
            if res[1] == opcodes['ack'] and res[3] == packet[3]: 
                print(f'Received ACK {res[3]}')
                packs_acked.add(packet[3])
                pack_acked = True 


    if max(packs_acked) == num_packets: 
        print('All packets sent and ACKed')
    else: 
        if len(packs_acked) > 0: 
            err_ins = max(packs_acked)
        else: 
            err_ins = None     
        raise RuntimeError(f'An Error Occurred: Last outbound packet ACKed was {err_ins}')


    socket.close()
    print('Connection closed')
    
    return 


def main(): 
    '''
    This function listens for incoming requests on the provided port number
    and once a request comes in, spins up another socket on which to complete 
    the transaction and continues listening for new requests on the main port 

    Depending on if the request is a RRQ or WRQ, the server calls either 
    handle_RRQ or handle_WRQ using the new socket 
    '''
    
    host = socket.gethostname()
    port = int(sys.argv[1])
    timeout = int(sys.argv[2]) / 1000
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Internet and UDP socket 
    s.bind((host, port))

    print(f'Listening on port {port}...')
    print(f'Timeout {timeout} secs')

    
    while True: 
        data, client = s.recvfrom(MAX_SIZE + 4) # 4 bytes for header, plus MAX_SIZE for data
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) 
        new_port = random.randint(1024, 65535)
        while new_port == port: 
            new_port = random.randint(1024, 65535)
        _s.bind((host, new_port))
        print(f'Connection on port {new_port}')
        file_path = extract_filepath(data)
        if data[1] == opcodes['read']: 
            handle_RRQ(file_path, client, _s, timeout)
        elif data[1] == opcodes['write']: 
            handle_WRQ(file_path, client, _s, timeout)    

if __name__ == '__main__': 
    main()
