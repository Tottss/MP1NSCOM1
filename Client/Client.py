import socket
import os
import time
from pathlib import Path
from Packet import Packet

client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_packet = None
server_packet = None
server_addr = None

def display_commands():
    print("COMMAND LISTS")
    print("/join <server_ip_add> <port>")
    print("/leave")
    print("/register <handle>")
    print("/store <filename>")
    print("/dir")
    print("/get <filename>")

def establish_connection(ipadd, port):
    print("Connecting to Server...")
    global server_addr, client_packet, server_packet
    server_addr = (ipadd, port)

    #client's ISN for this example is 69
    client_packet = Packet(mtype="SYN", seq_syn=69)
    #sending SYN to server
    client.sendto(client_packet.encode(), server_addr)

    #awaiting SYN-ACK from server
    raw_bytes, server_addr = client.recvfrom(1024)

    server_packet = Packet.decode(raw_bytes)

    if server_packet.mtype == "SYN-ACK":
        print(f"Acknowledged packet from {server_addr}")

        client_packet.mtype="ACK"
        client_packet.seq_syn = server_packet.seq_ack
        client_packet.seq_ack = server_packet.seq_syn + 1
        client.sendto(client_packet.encode(), server_addr)
    else:
        print("Error: Header is not \"SYN-ACK\"")

    #awaiting SYN-ACK from server
    raw_bytes, server_addr = client.recvfrom(1024)

    server_packet = Packet.decode(raw_bytes)

    if server_packet.mtype == "ACK":
        print(f"Acknowledged packet from {server_addr}")

        client_packet.mtype=""
        client_packet.seq_syn = server_packet.seq_ack
        client_packet.seq_ack = server_packet.seq_syn + 1
        print("Connection Succesful !")
    else:
        print("Error: Header is not \"ACK\"")

#Leave the connection
def leave_connection():
    global server_addr, client_packet, server_packet
    
    client_packet.mtype="FIN"
    client.sendto(client_packet.encode(), server_addr)

    #awaiting FIN-ACK from server
    raw_bytes, server_addr = client.recvfrom(1024)

    server_packet = Packet.decode(raw_bytes)

    if server_packet.mtype == "FIN-ACK":
        print(f"Acknowledged packet from {server_addr}")

        client_packet.mtype="ACK"
        client_packet.seq_syn = server_packet.seq_ack
        client_packet.seq_ack = server_packet.seq_syn + 1
        client.sendto(client_packet.encode(), server_addr)
    else:
        print("Error: Header is not \"FIN-ACK\"")

    raw_bytes, _ = client.recvfrom(1024)
    server_packet = Packet.decode(raw_bytes)
    
    if server_packet.mtype == "ACK":
        print("Disconnected from server")
    else:
        print("Error: Cannot Disconnect from Server")
        return False
    
    return True
    
def send_file(filename):
    global server_addr
    filesize = os.path.getsize(filename)
    
    # notify server of file details 
    start_pkt = Packet(mtype="STORE", payload=f"{filename}|{filesize}")
    client.sendto(start_pkt.encode(), server_addr)

    with open(filename, "rb") as f:
        seq = 1
        while True:
            chunk = f.read(512)
            if not chunk: break
            
            # Binary-safe encoding for JSON 
            payload_str = chunk.decode('latin-1') 
            data_pkt = Packet(mtype="DATA", seq_syn=seq, payload=payload_str)
            
            # Retransmission logic
            while True:
                client.sendto(data_pkt.encode(), server_addr)
                client.settimeout(2.0) # Timeout for lost packets
                try:
                    raw, _ = client.recvfrom(2048)
                    ack = Packet.decode(raw)
                    if ack.mtype == "ACK" and ack.seq_ack == seq:
                        seq += 1
                        break
                except socket.timeout:
                    print(f"Retransmitting packet {seq}...")
    
    # Termination: Send EOF
    client.sendto(Packet(mtype="EOF").encode(), server_addr)
    client.settimeout(None)
    print("Upload complete.")
        
def request_download(filename):
    global server_addr
    pkt = Packet(mtype="GET", payload=filename)
    client.sendto(pkt.encode(), server_addr)
    
    expected_seq = 1
    with open(f"received_{filename}", "wb") as f:
        while True:
            try:
                client.settimeout(5.0) 
                raw, addr = client.recvfrom(2048)
                pkt = Packet.decode(raw)
                #  File Not Found 
                if pkt.mtype == "ERROR":
                    print(f"Server Error: {pkt.payload}") 
                    return

                if pkt.mtype == "EOF":
                    print("Download complete.")
                    break
                
                if pkt.mtype == "DATA" and pkt.seq_syn == expected_seq:
                    f.write(pkt.payload.encode('latin-1'))
                    # Send ACK 
                    ack_pkt = Packet(mtype="ACK", seq_ack=expected_seq)
                    client.sendto(ack_pkt.encode(), server_addr)
                    expected_seq += 1
                else:
                    # Re-ACK last received sequence 
                    ack_pkt = Packet(mtype="ACK", seq_ack=expected_seq - 1)
                    client.sendto(ack_pkt.encode(), server_addr)
            except socket.timeout:
                print("Download timed out.")
                break
    client.settimeout(None)
    
            
def main():
    display_commands()
    flag = True

    while flag:
        prompt = input("> ").strip()
        if not prompt:
            print("Error: No command entered. Please try again.")
            continue  
        cmd_key = prompt.split()

        match cmd_key[0]:
            case "/join":
                if len(cmd_key) == 3:
                    ipadd = cmd_key[1]  # a string
                    port = int(cmd_key[2])  # an int

                    establish_connection(ipadd, port)
            
            case "/store":
                if len(cmd_key) == 2:
                    filename = cmd_key[1]
                    if os.path.exists(filename):
                        send_file(filename)
                    else:
                        print("Error: File not found locally.")
                        
            case "/get":
                    if len(cmd_key) == 2:
                        filename = cmd_key[1]
                        request_download(filename)
            case "/leave":
                if leave_connection():
                    flag = False
                    

main()