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

    max_retries = 3
    attempts = 0
    connected = False

    while attempts < max_retries:
        #sending SYN to server
        client.sendto(client_packet.encode(), server_addr)
        client.settimeout(2.0)

        try:
            #awaiting SYN-ACK from server
            raw_bytes, server_addr = client.recvfrom(1024)

            server_packet = Packet.decode(raw_bytes)

            if server_packet.mtype == "SYN-ACK":
                print(f"Acknowledged packet from {server_addr}")
                client_packet.mtype="ACK"
                client_packet.seq_syn = server_packet.seq_ack
                client_packet.seq_ack = server_packet.seq_syn + 1
                print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                connected = True
                break
            else:
                print("Error: Header is not \"SYN-ACK\"")
        except socket.timeout:
            attempts += 1
            print(f"Connection timeout. Retrying SYN {attempts}/{max_retries}...")

    if not connected:
        print("Error: Could not reach server.")
        return False
    
    attempts = 0
    connected = False

    #for the sequence numbers to be stable
    while attempts < max_retries:
        client.sendto(client_packet.encode(), server_addr)
        client.settimeout(2.0)

        try:
            raw_bytes, server_addr = client.recvfrom(1024)

            server_packet = Packet.decode(raw_bytes)

            if server_packet.mtype == "ACK":
                print(f"Acknowledged packet from {server_addr}")

                client_packet.mtype=""
                client_packet.seq_syn = server_packet.seq_ack
                client_packet.seq_ack = server_packet.seq_syn
                print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                print("Connection Succesful !")
                connected = True
                break
            else:
                print("Error: Header is not \"ACK\"")
        except socket.timeout:
            attempts += 1
            print(f"Connection timeout. Retrying ACK {attempts}/{max_retries}...")

    if not connected:
        print("Error: Could not reach server.")
        return False

    client.settimeout(None) 
    return True

#Leave the connection
def leave_connection():
    global server_addr, client_packet, server_packet
    
    client_packet.mtype="FIN"

    max_retries = 3
    attempts = 0
    fin_acked = False
    while attempts < max_retries:
        client.sendto(client_packet.encode(), server_addr)
        client.settimeout(2.0)
        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")

    #awaiting FIN-ACK from server
        try:
            raw_bytes, server_addr = client.recvfrom(1024)

            server_packet = Packet.decode(raw_bytes)

            if server_packet.mtype == "FIN-ACK":
                print(f"Acknowledged packet from {server_addr}")

                client_packet.mtype="ACK"
                client_packet.seq_syn = server_packet.seq_ack
                client_packet.seq_ack = server_packet.seq_syn + 1
                print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                fin_acked = True
                break
            else:
                print("Error: Header is not \"FIN-ACK\"")
        except socket.timeout:
            attempts += 1
            print(f"Timeout waiting for FIN-ACK. Retrying FIN {attempts}/{max_retries}...")

    if not fin_acked:
        print("Error: Server unresponsive. Forcing local disconnect.")
        client_packet.mtype = ""
        client_packet.seq_syn = 0
        client_packet.seq_ack = 0
        client_packet.payload_size = 0
        client_packet.payload = ""
        client.settimeout(None)
        return False
    
    attempts = 0  
    disconnected = False

    while attempts < max_retries:
        client.sendto(client_packet.encode(), server_addr)
        client.settimeout(2.0)

        try:
            raw_bytes, _ = client.recvfrom(1024)
            server_packet = Packet.decode(raw_bytes)
        
            if server_packet.mtype == "ACK":
                print("Disconnected from server")
                client_packet.mtype=""
                client_packet.seq_syn=0
                client_packet.seq_ack=0
                client_packet.payload_size=0
                client_packet.payload=""
                disconnected = True
                break
            else:
                print(f"Error: Header is not \"ACK\"")
        except socket.timeout:
            attempts += 1
            print(f"Timeout waiting for final ACK. Retrying ACK {attempts}/{max_retries}...")
        
    client.settimeout(None)
    
    if not disconnected:
        print("Error: Did not receive final ACK, but disconnected locally anyway.")
    
    return True
    
def send_file(filename):
    global server_addr, client_packet, server_packet
    filesize = os.path.getsize(filename)
    
    client_packet.mtype = "STORE"
    client_packet.payload = f"{filename}|{filesize}"
    
    max_retries = 3
    attempts = 0
    server_ready = False
    #Check if server is up
    while attempts < max_retries:
        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
        client.sendto(client_packet.encode(), server_addr)
        client.settimeout(3.0)
        
        try:
            raw, _ = client.recvfrom(2048)
            server_packet = Packet.decode(raw)
            if server_packet.mtype == "ACK":
                print(f"Server ready for upload: {filename}")
                server_ready = True
                break 
        except socket.timeout:
            attempts += 1
            print(f"Server did not acknowledge request. Retrying {attempts}/{max_retries}...")
            
    if not server_ready:
        print("Error: Server is cannot be reached.")
        return 

    #upload file
    with open(filename, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk: 
                break # End of file
            
            payload_str = chunk.decode('latin-1') 
            client_packet.mtype = "DATA"
            client_packet.seq_syn = server_packet.seq_ack
            client_packet.payload = payload_str

            chunk_attempts = 0
            chunk_acked = False
            
            #check if server is up while files is sending
            while chunk_attempts < max_retries:
                client.sendto(client_packet.encode(), server_addr)
                client.settimeout(2.0) 
                try:
                    raw, _ = client.recvfrom(2048)
                    server_packet = Packet.decode(raw)

                    if server_packet.mtype == "ACK":
                        client_packet.seq_syn += 1
                        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                        chunk_acked = True
                        break #  break inner loop
                except socket.timeout:
                    chunk_attempts += 1
                    print(f"Retransmitting packet {client_packet.seq_syn} ({chunk_attempts}/{max_retries})...")
            
            if not chunk_acked:
                print("Error: Server lost connection mid-upload.")
                return
            
    client_packet.mtype = "EOF"
    client_packet.payload_size = 0
    client_packet.payload = ""
    client.sendto(client_packet.encode(), server_addr)
    client.settimeout(None)
    print("Upload complete.")
        
def request_download(filename):
    global server_addr, client_packet, server_packet
    client_packet.mtype="GET"
    client_packet.payload=filename
    client.sendto(client_packet.encode(), server_addr)

    max_retries = 3
    attempts = 0
    
    with open(f"received_{filename}", "wb") as f:
        while attempts < max_retries:
            try:
                client.settimeout(5.0) 
                raw, addr = client.recvfrom(2048)
                server_packet = Packet.decode(raw)
                attempts = 0
                #  File Not Found 
                if server_packet.mtype == "ERROR":
                    print(f"Server Error: {server_packet.payload}") 
                    return
                
                if server_packet.mtype == "DATA":
                    if server_packet.seq_syn == client_packet.seq_ack:
                        f.write(server_packet.payload.encode('latin-1'))
                        # Send ACK 
                        client_packet.mtype="ACK"
                        client_packet.seq_ack += 1
                        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                        client.sendto(client_packet.encode(), server_addr)
                    else:
                        # Re-ACK last received sequence 
                        client_packet.mtype="ACK"
                        client_packet.seq_ack -= 1
                        print(f"Seq No for Client: {client_packet.seq_syn}, Seq No for Server: {client_packet.seq_ack}")
                        client.sendto(client_packet.encode(), server_addr)
                if server_packet.mtype == "EOF":
                    print("Download complete.")
                    break
            except socket.timeout:
                attempts += 1
                print(f"Packet lost. Retrying {attempts}/{max_retries}...")
                client.sendto(client_packet.encode(), server_addr)

            if attempts == max_retries:
                print("Error: Server stopped responding. Aborting download.")
                break
    f.close()

    client.settimeout(None)
    
            
def main():
    display_commands()
    flag = True
    is_connected = False

    while flag:
        prompt = input("> ").strip()
        if not prompt:
            print("Error: No command entered. Please try again.")
            continue  
        cmd_key = prompt.split()

        match cmd_key[0]:
            case "/join":
                if not is_connected:
                    if len(cmd_key) == 3:
                        ipadd = cmd_key[1]  # a string
                        port = int(cmd_key[2])  # an int

                        is_connected = establish_connection(ipadd, port)
                        
                else:
                    print("Error: You are already connected")
            
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