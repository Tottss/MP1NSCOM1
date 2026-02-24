import socket
import os
import random
from Packet import Packet
import hashlib

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_packet = None
server_packet = None

#toggle for retransmission simulation
SIMULATE_DROP = True
DROP_RATE = 0.10

def calculate_file_hash(filename):
    """Generates a SHA-256 hash for a given file."""
    sha256 = hashlib.sha256()
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(4096)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()

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
        return

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
        print(f"Acknowledged STORE from {client_addr}")

        if client_packet.payload == "YES" or client_packet.payload == "NO":
            print(f"Caught retransmitted '{client_packet.payload}'. Acknowledging.")
            server_packet.mtype = "ACK"
            server.sendto(server_packet.encode(), client_addr)
            return

        # Safe payload check
        if "|" not in client_packet.payload:
            print(f"Error: Malformed STORE payload received: '{client_packet.payload}'")
            return
            
        filename, _ = client_packet.payload.split('|')
        filename = filename.strip(" \x00")

        if os.path.exists(filename):
            print(f"File {filename} exists. Asking client for overwrite...")
            server_packet.mtype = "ERROR"
            server_packet.payload = "FILE_EXISTS"
            server.sendto(server_packet.encode(), client_addr)
            
            try:
                server.settimeout(10.0)
                raw, addr = server.recvfrom(1024)
                client_packet = Packet.decode(raw)
                
                if client_packet.payload == "NO":
                    print("Overwrite cancelled by client.")
                    server_packet.mtype = "ACK"
                    server.sendto(server_packet.encode(), client_addr)
                    return 
                    
                elif client_packet.payload != "YES":
                    print("Invalid response from client. Cancelling.")
                    return

            except (socket.timeout, ConnectionResetError):
                print("Client took too long to answer overwrite prompt. Aborting.")
                reset_connection_state()
                return

        print(f"Receiving: {filename}")
        server_packet.mtype="ACK"
        server_packet.seq_ack = client_packet.seq_syn + 1
        print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")
        server.sendto(server_packet.encode(), client_addr)
        
    else:
        print("Error: Header is not \"STORE\"")
        return
    
    max_retries = 3
    attempts = 0
    sim_count = 0
    with open(f"{filename}", "wb") as f:
        while True:
            try:
                server.settimeout(5.0)
                raw, addr = server.recvfrom(65535)
                client_packet = Packet.decode(raw)
                attempts = 0
                
                #drops packet to simulate retransmission
                if SIMULATE_DROP and client_packet.mtype == "DATA" and sim_count < 5:
                    if random.random() < DROP_RATE:
                        print(f"\n[!] SIMULATED DROP: Ignoring packet {client_packet.seq_syn}")
                        sim_count += 1
                        continue
                
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
                    f.close()
                    
                    received_hash = client_packet.payload
                    local_hash = calculate_file_hash(filename)
                    
                    if received_hash == local_hash:
                        print("\n[SUCCESS] Transfer finished. SHA-256 Hash verified perfectly!")
                    else:
                        print("\n[WARNING] Transfer finished, but file integrity check failed!")
                    print("Transfer finished.")
                    break
            except (socket.timeout, ConnectionResetError):
                attempts += 1
                print(f"Timeout waiting for DATA. Retrying ACK {attempts}/{max_retries}...")
                if attempts >= max_retries:
                    print("\nError: Client disconnected mid-upload. Aborting.")
                    f.close() 
                    os.remove(filename) # Clean up partial file
                    reset_connection_state()
                    return
                # Retransmit last ACK
                server.sendto(server_packet.encode(), client_addr)
    f.close()
          
#file download handler                    
def handle_download(client_addr):
    global client_packet, server_packet
    if client_packet.mtype == "GET":
        print(f"Acknowledged GET from {client_addr}")
        filename = client_packet.payload.strip(" \x00")
        
        if not os.path.exists(filename):
            print(f"Error: File '{filename}' not found on server.") 
            server_packet.mtype = "ERROR"
            server_packet.payload = "File not found"
            server.sendto(server_packet.encode(), client_addr)
            return 
        
        print(f"Sending: {filename}")
        filesize = os.path.getsize(filename)
        server_packet.mtype = "ACK"
        server_packet.payload = str(filesize)
        server_packet.seq_ack = client_packet.seq_syn + 1
        server.sendto(server_packet.encode(), client_addr)
    else:
        print("Error: Header is not \"GET\"")
        return

    max_retries = 3
    
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk: 
                break
            
            payload_str = chunk.decode('latin-1')
            server_packet.mtype = "DATA"
            server_packet.seq_syn = client_packet.seq_ack
            server_packet.payload = payload_str
            
            chunk_attempts = 0
            chunk_acked = False
            sim_count = 0

            while chunk_attempts < max_retries:
                server.sendto(server_packet.encode(), client_addr)
                server.settimeout(2.0)
                try:
                    raw, _ = server.recvfrom(2048)
                    client_packet = Packet.decode(raw)

                    #drops packet to simulate retransmission
                    if SIMULATE_DROP and client_packet.mtype == "DATA" and sim_count < 5:
                        if random.random() < DROP_RATE:
                            print(f"\n[!] SIMULATED DROP: Ignoring packet {client_packet.seq_syn}")
                            sim_count += 1
                            continue

                    if client_packet.mtype == "ACK":
                        server_packet.seq_syn += 1
                        chunk_acked = True
                        break
                except (socket.timeout, ConnectionResetError):
                    chunk_attempts += 1
                    print(f"Retransmitting packet {server_packet.seq_syn} ({chunk_attempts}/{max_retries})...")
                    
            if not chunk_acked:
                print("Client lost connection mid-download. Aborting.")
                reset_connection_state()
                return # Exit the function entirely

    # Send EOF to signal finish
    server_packet.mtype = "EOF"
    server_packet.payload_size = 0
    server_packet.payload = calculate_file_hash(filename)
    
    attempts = 0
    while attempts < max_retries:
        server.sendto(server_packet.encode(), client_addr)
        server.settimeout(2.0)
        try:
            raw, _ = server.recvfrom(2048)
            client_packet = Packet.decode(raw)
            if client_packet.mtype == "ACK":
                print("Download completed successfully.")
                # Sequence increments for EOF
                server_packet.seq_syn += 1 
                break
        except (socket.timeout, ConnectionResetError):
            attempts += 1
            print(f"Retrying EOF packet({attempts}/{max_retries})...")            
          
#Disconnect Client
def disconnect_connection(client_addr):
    global client_packet, server_packet
    print(f"Acknowledged packet from {client_addr}")

    server_packet.mtype="FIN-ACK"
    server_packet.seq_syn = client_packet.seq_ack
    server_packet.seq_ack = client_packet.seq_syn + 1
    print(f"Seq No for Client: {server_packet.seq_ack}, Seq No for Server: {server_packet.seq_syn}")

    max_retries = 3
    attempts = 0

    while attempts < max_retries:
        print(f"Seq No for Server: {server_packet.seq_syn}, Seq No for Client: {server_packet.seq_ack}")
        server.sendto(server_packet.encode(), client_addr)
        server.settimeout(2.0)

        try:
            raw_bytes, client_addr = server.recvfrom(1024)
            client_packet = Packet.decode(raw_bytes)

            if client_packet.mtype == "ACK":
                print(f"Acknowledged ACK from {client_addr}")
                server_packet.mtype = "ACK"
                server.sendto(server_packet.encode(), client_addr)
                print("Disconnected from Client cleanly.")
                reset_connection_state()
                return
            else:
                print("Error: Header is not \"ACK\"")
        except (socket.timeout, ConnectionResetError):
            attempts += 1
            print(f"Timeout waiting for FIN-ACK's ACK. Retrying {attempts}/{max_retries}...")
            
    print("Client unresponsive during disconnect. Forcing drop.")
    reset_connection_state()

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

