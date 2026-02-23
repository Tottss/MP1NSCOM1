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
    print("/store <filename>")
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
        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
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
        client_packet.seq_ack = server_packet.seq_syn
        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
        print("Connection Succesful !")
    else:
        print("Error: Header is not \"ACK\"")

#Leave the connection
def leave_connection():
    global server_addr, client_packet, server_packet
    
    client_packet.mtype="FIN"
    client.sendto(client_packet.encode(), server_addr)
    print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")

    #awaiting FIN-ACK from server
    raw_bytes, server_addr = client.recvfrom(1024)

    server_packet = Packet.decode(raw_bytes)

    if server_packet.mtype == "FIN-ACK":
        print(f"Acknowledged packet from {server_addr}")

        client_packet.mtype="ACK"
        client_packet.seq_syn = server_packet.seq_ack
        client_packet.seq_ack = server_packet.seq_syn + 1
        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
        client.sendto(client_packet.encode(), server_addr)
    else:
        print("Error: Header is not \"FIN-ACK\"")

    raw_bytes, _ = client.recvfrom(1024)
    server_packet = Packet.decode(raw_bytes)
    
    if server_packet.mtype == "ACK":
        print("Disconnected from server")
        client_packet.mtype=""
        client_packet.seq_syn=0
        client_packet.seq_ack=0
        client_packet.payload_size=0
        client_packet.payload=""
    else:
        print("Error: Cannot Disconnect from Server")
        return False
    
    return True
    
def send_file(filename):
    global server_addr, client_packet, server_packet
    filesize = os.path.getsize(filename)
    
    # notify server of file details 
    client_packet.mtype="STORE"
    client_packet.payload=f"{filename}|{filesize}"
    print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
    client.sendto(client_packet.encode(), server_addr)
    
    try:
        client.settimeout(2.0)
        raw, _ = client.recvfrom(2048)
        server_packet = Packet.decode(raw)
        if server_packet.mtype == "ACK":
            print(f"Server ready for upload: {filename}")
    except socket.timeout:
        print("Server did not acknowledge upload request.")
        return

    if server_packet.mtype == "ACK":
        print(f"Acknowledged packet from {server_addr}")
    else:
        print("Error: Header is not \"ACK\"")

    with open(filename, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk: break
            
            # Binary-safe encoding for JSON 
            payload_str = chunk.decode('latin-1') 

            client_packet.mtype="DATA"
            client_packet.seq_syn = server_packet.seq_ack
            client_packet.payload=payload_str

            # Retransmission logic
            while True:
                client.sendto(client_packet.encode(), server_addr)
                client.settimeout(2.0) # Timeout for lost packets
                try:
                    raw, _ = client.recvfrom(2048)
                    server_packet = Packet.decode(raw)

                    if server_packet.mtype == "ACK":
                        client_packet.seq_syn += 1
                        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                        break
                except socket.timeout:
                    print(f"Retransmitting packet {client_packet.seq_syn}...")
    f.close()
    
    # Termination: Send EOF
    client_packet.mtype="EOF"
    client_packet.payload = ""
    client.sendto(client_packet.encode(), server_addr)
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
    f.close()

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