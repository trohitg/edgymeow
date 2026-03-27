# EdgyMeow - Python Client

Async Python client for the [EdgyMeow](https://github.com/trohitg/edgymeow) WebSocket API.

## Installation

```bash
pip install edgymeow
```

Requires the EdgyMeow server running separately:

```bash
npm install -g edgymeow
npx edgymeow start
```

## Usage

```python
import asyncio
from edgymeow import WhatsAppRPCClient

async def main():
    client = WhatsAppRPCClient("ws://localhost:9400/ws/rpc")
    await client.connect()

    # Check status
    status = await client.status()
    print(status)

    # Send a text message
    await client.send(phone="1234567890", type="text", message="Hello!")

    # Send an image
    await client.send(
        phone="1234567890",
        type="image",
        media_data={
            "data": "<base64>",
            "mime_type": "image/jpeg",
            "caption": "Check this out!"
        }
    )

    # List groups
    groups = await client.groups()

    # Get chat history
    history = await client.chat_history(phone="1234567890", limit=50)

    # List subscribed channels
    channels = await client.newsletters()

    # Get channel stats
    stats = await client.newsletter_stats(jid="123456789@newsletter", count=20)

    await client.close()

asyncio.run(main())
```

## Events

```python
async def main():
    client = WhatsAppRPCClient("ws://localhost:9400/ws/rpc")

    def on_event(event):
        if event["method"] == "event.message_received":
            print(f"New message: {event['params']['text']}")

    client.event_callback = on_event
    await client.connect()

    # Keep running to receive events
    await asyncio.sleep(3600)
    await client.close()
```

## API Methods

| Method | Description |
|--------|-------------|
| `status()` | Get connection status |
| `start()` / `stop()` / `restart()` | Control WhatsApp service |
| `qr()` | Get QR code for pairing |
| `send(**kwargs)` | Send message (text, image, video, audio, document, location, contact) |
| `media(message_id)` | Download media from message |
| `groups()` | List all groups |
| `group_info(group_id)` | Get group details |
| `contacts(query)` | List contacts |
| `contact_check(phones)` | Check WhatsApp registration |
| `chat_history(**kwargs)` | Get message history |
| `typing(jid, state)` | Send typing indicator |
| `presence(status)` | Set online/offline |
| `mark_read(message_ids, chat_jid)` | Mark messages as read |
| `rate_limit_get()` / `rate_limit_set(**config)` | Rate limiting config |
| `newsletters(refresh)` | List subscribed channels |
| `newsletter_info(jid, invite, refresh)` | Get channel details |
| `newsletter_create(name, description, picture)` | Create a channel |
| `newsletter_follow(jid)` | Subscribe to a channel |
| `newsletter_unfollow(jid)` | Unsubscribe from a channel |
| `newsletter_mute(jid, mute)` | Mute/unmute a channel |
| `newsletter_messages(jid, count, before)` | Get channel messages |
| `newsletter_send(group_id, type, message, media_data)` | Send to channel (admin only) |
| `newsletter_mark_viewed(jid, server_ids)` | Mark messages as viewed |
| `newsletter_react(jid, server_id, reaction)` | React to a channel message |
| `newsletter_live_updates(jid)` | Subscribe to live updates |
| `newsletter_stats(jid, invite, count)` | Get channel statistics |

## License

MIT
