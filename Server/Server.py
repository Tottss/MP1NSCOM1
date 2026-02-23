import socket
import os
from Packet import Packet

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_packet = None
server_packet = None

#Establish connection
def awaiting_connection(client_addr):
    global client_packet, server_packet
    print("Server waiting for connection...")

    #awaiting SYN from client

    if client_packet.mtype == "SYN":
        print(f"Acknowledged packet from {client_addr}")

         #client's ISN for this example is 67
        server_packet = Packet(mtype="SYN-ACK", seq_syn = 67, seq_ack = client_packet.seq_syn + 1)
        server.sendto(server_packet.encode(), client_addr)
    else:
        print("Error: Header is not \"SYN\"")

    #awaiting ACK from client
    raw_bytes, client_addr = server.recvfrom(1024)

    client_packet = Packet.decode(raw_bytes)

    if client_packet.mtype == "ACK":
        print(f"Acknowledged packet from {client_addr}")

        server_packet.mtype="ACK"
        server_packet.seq_syn = client_packet.seq_ack
        server_packet.seq_ack = client_packet.seq_syn + 1
        server.sendto(server_packet.encode(), client_addr)
        print("Connection Established")
    else:
        print("Error: Header is not \"ACK\"")
        
        
def receive_file(init_packet, client_addr):
    filename, _ = init_packet.payload.split('|')
    print(f"Receiving: {filename}")
    
    expected_seq = 1
    with open(f"{filename}", "wb") as f:
        while True:
            raw, addr = server.recvfrom(2048)
            pkt = Packet.decode(raw)
            
            if pkt.mtype == "EOF": # End of file signaling
                print("Transfer finished.")
                break
            
            if pkt.mtype == "DATA":
                if pkt.seq_syn == expected_seq: # Verify sequence 
                    f.write(pkt.payload.encode('latin-1')) # Binary-safe
                    
                    # Send ACK
                    ack_pkt = Packet(mtype="ACK", seq_ack=expected_seq)
                    server.sendto(ack_pkt.encode(), client_addr)
                    expected_seq += 1
                else:
                    # Session mismatch
                    ack_pkt = Packet(mtype="ACK", seq_ack=expected_seq-1)
                    server.sendto(ack_pkt.encode(), client_addr)
          
#file download handler                    
def handle_download(request_pkt, client_addr):
    filename = request_pkt.payload
    print(f"Client requested: {filename}")
    
    #Check if file exists 
    if not os.path.exists(filename):
        err_pkt = Packet(mtype="ERROR", payload="File not found")
        server.sendto(err_pkt.encode(), client_addr)
        return

    with open(filename, "rb") as f:
        seq = 1
        while True:
            chunk = f.read(512)
            if not chunk: break
            
            payload_str = chunk.decode('latin-1')
            data_pkt = Packet(mtype="DATA", seq_syn=seq, payload=payload_str)
            
            while True:
                server.sendto(data_pkt.encode(), client_addr)
                server.settimeout(2.0)
                try:
                    raw, _ = server.recvfrom(2048)
                    ack = Packet.decode(raw)
                    if ack.mtype == "ACK" and ack.seq_ack == seq:
                        seq += 1
                        break
                except socket.timeout:
                    print(f"Retransmitting packet {seq} to client...")
    
    # Send EOF to signal finish
    server.sendto(Packet(mtype="EOF").encode(), client_addr)
    server.settimeout(None)              
          
#Disconnect Client
def disconnect_connection(client_addr):
    global client_packet, server_packet
    print(f"Acknowledged packet from {client_addr}")

    server_packet.mtype="FIN-ACK"
    server_packet.seq_syn = client_packet.seq_ack
    server_packet.seq_ack = client_packet.seq_syn + 1
    server.sendto(server_packet.encode(), client_addr)

    #awaiting ACK from client
    raw_bytes, client_addr = server.recvfrom(1024)

    client_packet = Packet.decode(raw_bytes)

    if client_packet.mtype == "ACK":
        print(f"Acknowledged packet from {client_addr}")

        server_packet.mtype="ACK"
        server_packet.seq_syn = 0
        server_packet.seq_ack = 0
        server.sendto(server_packet.encode(), client_addr)
        print("Disconnected from Client")
    else:
        print("Error: Header is not \"ACK\"")

#start server
def start():
    global client_packet, server_packet
    server.bind(('127.0.0.1', 12345))
    print("SERVER ON")
    flag = True

    while flag:
        raw_bytes, client_addr = server.recvfrom(1024)

        client_packet = Packet.decode(raw_bytes)
        
        match client_packet.mtype:
            case "SYN":
                awaiting_connection(client_addr)
            case "STORE":
                receive_file(client_packet, client_addr)
            case "GET":
                handle_download(client_packet, client_addr)
            case "FIN":
                disconnect_connection(client_addr)

start()

