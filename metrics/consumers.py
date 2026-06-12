import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MetricConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.host_id = self.scope['url_route']['kwargs'].get('host_id')
        
        if self.host_id:
            # Route specific to a single host
            self.group_name = f"metrics_host_{self.host_id}"
        else:
            # Global monitoring route
            self.group_name = "metrics_all"

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # Receive message from WebSocket (client to server)
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # We can handle custom actions from client if needed here
            action = data.get('action')
            if action == 'ping':
                await self.send(text_data=json.dumps({'status': 'pong'}))
        except Exception as e:
            pass

    # Custom handlers for events dispatched via group_send
    async def metric_update(self, event):
        # Send metric update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'metric_update',
            'data': event['data']
        }))

    async def alert_update(self, event):
        # Send alert notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'alert_update',
            'data': event['data']
        }))
