import json
# import pprint
# import string
# import random
import time
from functools import partial

from channels.generic.websocket import WebsocketConsumer
# from channels.generic.websocket import AsyncJsonWebsocketConsumer
# from asgiref.sync import async_to_sync

from chain_parser import ChainParser
from graph_visualisation import GraphVisualisation


# class ComplexUserInterfaceConsumer(AsyncJsonWebsocketConsumer):
#     async def connect(self):
#         letters = string.ascii_lowercase
#         result_str = ''.join(random.choice(letters) for i in range(20))
#         self.room_group_name = result_str  # 'test'
#
#         print(f"User: {self.room_group_name}")
#
#         await self.channel_layer.group_add(
#             self.room_group_name,
#             self.channel_name
#         )
#
#         await self.accept()
#
#     async def receive(self, text_data):
#         text_data_json = json.loads(text_data)
#         message = text_data_json['message']
#
#         await self.channel_layer.group_send(
#             self.room_group_name,
#             {
#                 'type': 'chat_message',
#                 'message': message
#             }
#         )
#
#     async def chat_message(self, event):
#         message = event['message']
#
#         await self.send(text_data=json.dumps({
#             'type': 'chat',
#             'message': message
#         }))
#
#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(
#             self.room_group_name,
#             self.channel_name
#         )


class UserInterfaceConsumer(WebsocketConsumer):
    def connect(self):
        self.accept()

        self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': '.'
        }))

    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        tag = text_data_json['type']
        if tag == "start_parsing":
            print("start_parsing tag found!")
            data = text_data_json['data']
            print(f"Data received: {data}")
            send_message(self.send, 'Process started...')

            file_name = start_search(self.send, data['address_input'], int(data['layer_input']))

            print(f"Filename is: {file_name}")
            if file_name != "":
                self.send(text_data=json.dumps({
                    'type': 'svg_file',
                    'svg_file_name': file_name
                }))

        else:
            print(f"Message received: {message}")
            print(f"Tag of that message: {tag}")

            self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'I received your message, dummy!'
            }))


def display_logs(send_function):
    print(f"Inside display_logs!")
    for i in range(5):
        send_function(json.dumps(
            {
                'type': 'chat_message',
                'message': f"Message #{i}"
            }
        ))
        time.sleep(1)
    return "transaction-graph-15.gv.svg"


def send_message(send_function, message, message_type='chat_message'):
    send_function(json.dumps({
        'type': message_type,
        'message': message
    }))


def start_search(send_function, address, layer_nb):
    send_function_bis = partial(send_message, send_function)

    chain_parser = ChainParser(address, layer_nb, send_fct=send_function_bis)
    res = chain_parser.start_analysis()  # Res is True if the parsing was successful, False otherwise.
    if res:
        chain_parser.get_statistics()

        tree = GraphVisualisation(chain_parser.transaction_lists)
        file_name = tree.build_tree()
        return file_name
    return ""
