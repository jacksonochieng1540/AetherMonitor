import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MetricConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.host_id = self.scope['url_route']['kwargs'].get('host_id')
        
        if self.host_id:
            self.group_name = f"metrics_host_{self.host_id}"
        else:
            self.group_name = "metrics_all"
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            action = data.get('action')
            if action == 'ping':
                await self.send(text_data=json.dumps({'status': 'pong'}))
        except Exception as e:
            pass

    async def metric_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'metric_update',
            'data': event['data']
        }))

    async def alert_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'alert_update',
            'data': event['data']
        }))
