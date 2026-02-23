import socket
import os
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
    
def main():
    display_commands()
    flag = True

    while flag:
        prompt = input("> ").strip()
        if not prompt:
            print("Error: No command entered. Please try again.")
            continue  # Skip this iteration and go back to prompting the user
        cmd_key = prompt.split()

        match cmd_key[0]:
            case "/join":
                if len(cmd_key) == 3:
                    ipadd = cmd_key[1]  # a string
                    port = int(cmd_key[2])  # an int

                    establish_connection(ipadd, port)
            case "/leave":
                if leave_connection():
                    flag = False

main()