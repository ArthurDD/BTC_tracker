import ast
import json
import time
from functools import partial
from django.template.loader import render_to_string

from channels.generic.websocket import WebsocketConsumer

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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chain_parser = None
        self.manual = False
        self.finished_analysis = False

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
            self.finished_analysis = False
            data = text_data_json['data']
            send_message(self.send, 'Process started...')
            manual_mode = 'manual_input' in data
            address = data['address_input'].strip()

            success = self.start_search(self.send, address, rto_threshold=float(data['rto_input']),
                                        backward_layers=int(data['backward_layer_input']),
                                        forward_layers=int(data['forward_layer_input']), manual_mode=manual_mode)

            if success and not manual_mode:  # If the parsing was successful and we're not in manual mode (i.e all done)
                self.build_graph()

        elif tag == 'resume_parsing':   # Only called if manual mode is selected, message sent by "confirm" btn in modal
            print(f"Tx to remove: {message}")
            self.resume_analysis(ast.literal_eval(message)['tx_to_remove'])
            # Analyse next layer, stops if it was the last one

            if self.finished_analysis:
                self.build_graph()  # Done

        elif tag == "ba_report":
            self.get_ba_report(message)

        elif tag == "get_stats":
            html = render_to_string('user_interface/stats.html', {'data': self.chain_parser.transaction_tags})
            send_message(self.send, html, message_type='display_stats')

        else:
            print(f"Message received: {message}")
            print(f"Tag of that message: {tag}")

            self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'I received your message, dummy!'
            }))

    def start_search(self, send_function, address, backward_layers, forward_layers, rto_threshold, manual_mode):
        """
        Method only called once to start the parsing. If it returns false, error encountered, so we need to start
        the parsing again.
        :param rto_threshold:
        :param send_function:
        :param address:
        :param backward_layers:
        :param forward_layers:
        :param manual_mode:
        :return:
        """
        send_function_bis = partial(send_message, send_function)

        self.manual = manual_mode
        self.chain_parser = ChainParser(address, backward_layers=backward_layers, forward_layers=forward_layers,
                                        rto_threshold=rto_threshold, send_fct=send_function_bis)

        scraping_results = self.chain_parser.web_scraper.start_scraping()
        send_message(self.send, message="Scraping done!")
        html = render_to_string('user_interface/web_scraping_info.html', scraping_results)
        send_message(self.send, html, message_type='scraping_results')

        send_message(self.send, message="Parsing started...")
        if self.manual:
            res = self.chain_parser.start_manual_analysis(display_partial_graph=True)
            # Res is True if the parsing of the wallet was successful, False otherwise.
        else:
            res = self.chain_parser.start_analysis(display_partial_graph=True)

        # manual_tx message is sent in select_inputs method called inside start_manual_analysis if manual == True.
        return res

    def resume_analysis(self, tx_to_remove):
        self.chain_parser.start_manual_analysis(tx_to_remove=tx_to_remove,  display_partial_graph=True)
        # manual_tx message is sent in select_inputs method called inside start_analysis if manual == True.
        # Need to call this function even when self.finished_analysis == True bc we still need to parse the last layer

        # This case is to make the transition between the last backward layer parsed and the first forward layer
        if self.chain_parser.layer_counter - 1 >= self.chain_parser.nb_layers and \
                self.chain_parser.forward_layer_counter == 1:
            self.chain_parser.start_manual_analysis(tx_to_remove=[], display_partial_graph=True)

        elif (self.chain_parser.layer_counter - 1 >= self.chain_parser.nb_layers
              or self.chain_parser.layer_counter == 0) \
            and (self.chain_parser.forward_layer_counter == 0
                 or self.chain_parser.forward_layer_counter - 1 >= self.chain_parser.forward_nb_layers):
            # If there is no more layer to parse
            self.finished_analysis = True

    def build_graph(self):
        """
        Builds the final graph
        :return: None
        """
        self.chain_parser.get_statistics()  # Calculates the stats that will be later displayed when front end
        # receives a message whose message_type == svg_file

        tree = GraphVisualisation(self.chain_parser.transaction_lists, backward_layers=self.chain_parser.nb_layers,
                                  forward_layers=self.chain_parser.forward_nb_layers,
                                  backward_root_value=self.chain_parser.root_value,
                                  forward_root_value=self.chain_parser.forward_root_value)
        file_name = tree.build_tree()

        html_graph = render_to_string('user_interface/tree.html', {'file_name': file_name})
        html_charts = render_to_string('user_interface/charts.html')
        html_stats = render_to_string('user_interface/stats.html', {'data': self.chain_parser.transaction_tags})

        if file_name != "":
            self.send(text_data=json.dumps({
                'type': 'svg_file',
                'message': {'html_graph': html_graph, 'html_charts': html_charts, 'html_stats': html_stats}
            }))

    def get_ba_report(self, address):
        report = self.chain_parser.web_scraper.bitcoinabuse_search(address)

        html_stats = render_to_string('user_interface/ba_search_results.html', {'report': report})
        self.send(text_data=json.dumps({
            'type': 'ba_report',
            'message': {'ba_report_html': html_stats, 'address': address}
        }))


def send_message(send_function, message, message_type='chat_message'):
    """
    Function to send messages through the websocket
    :param send_function: send function from UserInterfaceConsumer
    :param message: Message to send
    :param message_type: Type of the message
    :return: None
    """
    send_function(json.dumps({
        'type': message_type,
        'message': message
    }))


def display_logs(send_function):
    """
    For testing purposes only -- Not used in deployment version.
    :param send_function:
    :return:
    """
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
