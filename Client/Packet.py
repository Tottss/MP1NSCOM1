import json

class Packet:

    def __init__(self, mtype, seq_syn=0, seq_ack=0, payload_size=0 , payload=""):
        self.mtype = mtype
        self.seq_syn = seq_syn
        self.seq_ack = seq_ack
        self.payload_size = payload_size
        self.payload = payload

    def encode(self):
        return json.dumps(self.__dict__).encode('utf-8')
    
    @staticmethod
    def decode(raw_bytes):
        data = json.loads(raw_bytes.decode('utf-8'))
        return Packet(**data)