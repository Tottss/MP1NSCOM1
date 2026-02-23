import socket
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
            case "FIN":
                disconnect_connection(client_addr)

start()