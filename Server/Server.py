import socket
import os
from Packet import Packet

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_packet = None
server_packet = None

def reset_connection_state():
    global client_packet, server_packet
    if server_packet:
        server_packet.mtype = ""
        server_packet.seq_syn = 0
        server_packet.seq_ack = 0
        server_packet.payload_size = 0
        server_packet.payload = ""
    if client_packet:
        client_packet.mtype = ""
        client_packet.seq_syn = 0
        client_packet.seq_ack = 0
        client_packet.payload_size = 0
        client_packet.payload = ""
    print("Deleting session, waiting for new client...\n")

#Establish connection
def awaiting_connection(client_addr):
    global client_packet, server_packet
    print("Server waiting for connection...")

    #awaiting SYN from client

    if client_packet.mtype == "SYN":
        print(f"Acknowledged packet from {client_addr}")

         #client's ISN for this example is 67
        server_packet = Packet(mtype="SYN-ACK", seq_syn = 67, seq_ack = client_packet.seq_syn + 1)
        print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
    else:
        print("Error: Header is not \"SYN\"")

    max_retries = 3
    attempts = 0
    connected = False

    #awaiting ACK from client
    while attempts < max_retries:
        server.sendto(server_packet.encode(), client_addr)
        server.settimeout(5.0)

        try:
            raw_bytes, client_addr = server.recvfrom(1024)
            client_packet = Packet.decode(raw_bytes)

            if client_packet.mtype == "ACK":
                print(f"Acknowledged packet from {client_addr}")

                server_packet.mtype="ACK"
                server_packet.seq_syn = client_packet.seq_ack
                server_packet.seq_ack = client_packet.seq_syn 
                print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
                server.sendto(server_packet.encode(), client_addr)
                print("Connection Established")
                connected = True
                break
            else:
                print("Error: Header is not \"ACK\"")
        except (socket.timeout, ConnectionResetError):
            attempts += 1
            print(f"Timeout waiting for final ACK. Retrying SYN-ACK {attempts}/{max_retries}...")

    if not connected:
        print("Client unresponsive during handshake.")
        reset_connection_state()
        
        
def receive_file(client_addr):
    global client_packet, server_packet
    if client_packet.mtype == "STORE":
        print(f"Acknowledged packet from {client_addr}")
        filename, _ = client_packet.payload.split('|')
        filename.strip(" \x00")
        # Check if file exists
        if os.path.exists(filename):
            print(f"File {filename} exists. Asking client for overwrite...")
            server_packet.mtype = "ERROR"
            server_packet.payload = "FILE_EXISTS"
            server.sendto(server_packet.encode(), client_addr)
            
            # Wait for client's decision
            raw, addr = server.recvfrom(1024)
            client_packet = Packet.decode(raw)
            
            if client_packet.payload != "YES":
                print("Overwrite cancelled by client.")
                return 
        print(f"Receiving: {filename}")
        server_packet.mtype="ACK"
        server_packet.seq_ack = client_packet.seq_syn + 1
        print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
        server.sendto(server_packet.encode(), client_addr)
    else:
        print("Error: Header is not \"STORE\"")
    
    with open(f"{filename}", "wb") as f:
        while True:
            raw, addr = server.recvfrom(2048)
            client_packet = Packet.decode(raw)
            print(client_packet.mtype)
            
            
            if client_packet.mtype == "DATA":
                if client_packet.seq_syn == server_packet.seq_ack: # Verify sequence 
                    f.write(client_packet.payload.encode('latin-1')) # Binary-safe
                    
                    # Send ACK
                    server_packet.mtype="ACK"
                    server_packet.seq_ack += 1
                    print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
                    server.sendto(server_packet.encode(), client_addr)
                else:
                    # Session mismatch
                    server_packet.mtype="ACK"
                    server_packet.seq_ack -= 1
                    print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
                    server.sendto(server_packet.encode(), client_addr)
            if client_packet.mtype == "EOF": # End of file signaling
                server_packet.mtype="ACK"
                server_packet.seq_ack += 1
                server.sendto(server_packet.encode(), client_addr)
                print("Transfer finished.")
                break
    f.close()
          
#file download handler                    
def handle_download(client_addr):
    global client_packet, server_packet
    if client_packet.mtype == "GET":
        print(f"Acknowledged packet from {client_addr}")
        filename = client_packet.payload.strip(" \x00")
        
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found on server.") 
            server_packet.mtype = "ERROR"
            server_packet.payload = "File not found"
            server.sendto(server_packet.encode(), client_addr)
            return 
        
        print(f"Sending: {filename}")
        filesize = os.path.getsize(filename)
        server_packet.mtype="ACK"
        server_packet.payload = str(filesize)
        server_packet.seq_ack = client_packet.seq_syn + 1
        print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
        
        server.sendto(server_packet.encode(), client_addr)
    else:
        print("Error: Header is not \"GET\"")

    print(f"Client requested: {filename}")
    
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk: break
            
            payload_str = chunk.decode('latin-1')
            server_packet.mtype="DATA"
            server_packet.seq_syn = client_packet.seq_ack
            server_packet.payload=payload_str
            
            while True:
                server.sendto(server_packet.encode(), client_addr)
                server.settimeout(2.0)
                try:
                    raw, _ = server.recvfrom(2048)
                    client_packet = Packet.decode(raw)
                    if client_packet.mtype == "ACK":
                        server_packet.seq_syn += 1
                        print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
                        break
                except socket.timeout:
                    print(f"Retransmitting packet {server_packet.seq_syn} to client...")
    f.close()

    # Send EOF to signal finish
    server_packet.mtype="EOF"
    server_packet.payload_size=0
    server_packet.payload=""
    server.sendto(server_packet.encode(), client_addr)
    server.settimeout(None)              
          
#Disconnect Client
def disconnect_connection(client_addr):
    global client_packet, server_packet
    print(f"Acknowledged packet from {client_addr}")

    server_packet.mtype="FIN-ACK"
    server_packet.seq_syn = client_packet.seq_ack
    server_packet.seq_ack = client_packet.seq_syn + 1
    print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
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
        server_packet.mtype=""
        server_packet.payload_size=0
        server_packet.payload=""
        print("Disconnected from Client")
    else:
        print("Error: Header is not \"ACK\"")

#start server
def start():
    global client_packet, server_packet
    server.bind(('127.0.0.1', 12345))
    print("SERVER ON")
    server.settimeout(1.0)

    try:
        while True:
            try:
                raw_bytes, client_addr = server.recvfrom(1024)

                client_packet = Packet.decode(raw_bytes)
                    
                match client_packet.mtype:
                    case "SYN":
                        awaiting_connection(client_addr)
                    case "STORE":
                        receive_file(client_addr)
                    case "GET":
                        handle_download(client_addr)
                    case "FIN":
                        disconnect_connection(client_addr)
            except (socket.timeout, ConnectionResetError):
                continue

    except KeyboardInterrupt:
        print("\nSERVER OFF")
        server.close()
                    

start()

