from django.urls import re_path
from user_interface.consumers import UserInterfaceConsumer


websocket_urlpatterns = [
    re_path(r'ws/connect/', UserInterfaceConsumer.as_asgi()),
]

