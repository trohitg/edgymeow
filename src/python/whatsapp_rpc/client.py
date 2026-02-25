"""
WhatsApp RPC Client - Async JSON-RPC 2.0 client over WebSocket

Uses the official `websockets` library for stable async WebSocket communication.
Implements JSON-RPC 2.0 protocol for bidirectional communication with Go backend.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Optional

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class WhatsAppRPCClient:
    """Async JSON-RPC 2.0 client using official websockets library."""

    def __init__(self, ws_url: str):
        """
        Initialize RPC client.

        Args:
            ws_url: WebSocket URL (e.g., 'ws://localhost:9400/ws/rpc')
        """
        self.ws_url = ws_url
        self.ws = None
        self.request_id = 0
        self.pending: dict[int, asyncio.Future] = {}
        self.event_callback: Optional[Callable[[dict], None]] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._connected = False

    @property
    def connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self._connected and self.ws is not None

    async def connect(self) -> None:
        """Connect to WebSocket RPC endpoint."""
        try:
            self.ws = await websockets.connect(
                self.ws_url,
                ping_interval=300,  # 5 minutes, same as Go server
                ping_timeout=60,
                max_size=100 * 1024 * 1024,  # 100 MB max message size for large media
                close_timeout=10,
            )
            self._connected = True
            self._recv_task = asyncio.create_task(self._receive_loop())
            logger.info(f"Connected to RPC endpoint: {self.ws_url}")
        except Exception as e:
            logger.error(f"Failed to connect to RPC endpoint: {e}")
            raise

    async def close(self) -> None:
        """Close connection."""
        self._connected = False
        if self._recv_task:
            self._recv_task.cancel()
            try:
                await self._recv_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
            self.ws = None
        logger.info("RPC connection closed")

    async def _receive_loop(self) -> None:
        """Handle incoming messages (responses and events)."""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)

                    if "id" in data and data["id"] is not None:
                        # Response to a request
                        req_id = data["id"]
                        if req_id in self.pending:
                            self.pending[req_id].set_result(data)
                    elif data.get("method", "").startswith("event."):
                        # Event notification from server
                        if self.event_callback:
                            try:
                                self.event_callback(data)
                            except Exception as e:
                                logger.error(f"Error in event callback: {e}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON received: {e}")
        except ConnectionClosed:
            logger.warning("WebSocket connection closed")
            self._connected = False
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            self._connected = False

    async def call(self, method: str, params: Any = None, timeout: float = 30) -> Any:
        """
        Call RPC method and wait for response.

        Args:
            method: RPC method name (e.g., 'status', 'send')
            params: Method parameters (optional)
            timeout: Response timeout in seconds

        Returns:
            Result from the RPC call

        Raises:
            Exception: If RPC call fails or times out
        """
        if not self.connected:
            raise Exception("Not connected to RPC endpoint")

        self.request_id += 1
        req_id = self.request_id

        request = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            request["params"] = params

        future = asyncio.get_event_loop().create_future()
        self.pending[req_id] = future

        try:
            await self.ws.send(json.dumps(request))
            response = await asyncio.wait_for(future, timeout)

            if "error" in response and response["error"]:
                error = response["error"]
                raise Exception(f"RPC Error {error.get('code', -1)}: {error.get('message', 'Unknown error')}")

            return response.get("result")
        except asyncio.TimeoutError:
            raise Exception(f"RPC call '{method}' timed out after {timeout}s")
        finally:
            self.pending.pop(req_id, None)

    # Convenience methods for each RPC command
    async def status(self) -> dict:
        """Get WhatsApp connection status."""
        return await self.call("status")

    async def start(self) -> dict:
        """Start WhatsApp service."""
        return await self.call("start")

    async def stop(self) -> dict:
        """Stop WhatsApp service."""
        return await self.call("stop")

    async def restart(self) -> dict:
        """Restart WhatsApp service."""
        return await self.call("restart")

    async def reset(self) -> dict:
        """Reset WhatsApp session."""
        return await self.call("reset")

    async def diagnostics(self) -> dict:
        """Get diagnostics information."""
        return await self.call("diagnostics")

    async def qr(self) -> dict:
        """Get QR code for pairing."""
        return await self.call("qr")

    async def send(self, **kwargs) -> dict:
        """
        Send WhatsApp message.

        Supports all message types: text, image, video, audio, document,
        sticker, location, contact.

        Args:
            phone: Recipient phone number (or use group_id)
            group_id: Group JID (or use phone)
            type: Message type (text, image, etc.)
            message: Text content (for text messages)
            media_data: Media content (for media messages)
            location: Location data (for location messages)
            contact: Contact data (for contact messages)
            reply: Reply context (optional)
        """
        return await self.call("send", kwargs)

    async def media(self, message_id: str) -> dict:
        """
        Download media from a received message.

        Args:
            message_id: ID of the message containing media

        Returns:
            Dict with 'data' (base64) and 'mime_type'
        """
        # Use longer timeout for media downloads (videos can be large)
        return await self.call("media", {"message_id": message_id}, timeout=120)

    async def groups(self) -> list:
        """
        Get all groups the user is a member of.

        Returns:
            List of group info dicts with jid, name, topic, participants, etc.
        """
        return await self.call("groups")

    async def group_info(self, group_id: str) -> dict:
        """
        Get detailed information about a specific group.

        Args:
            group_id: Group JID (e.g., '123456789@g.us')

        Returns:
            Dict with group details including participants
        """
        return await self.call("group_info", {"group_id": group_id})

    async def group_update(self, group_id: str, name: str = None, topic: str = None) -> dict:
        """
        Update group name and/or topic (description).

        Args:
            group_id: Group JID
            name: New group name (optional)
            topic: New group description (optional)

        Returns:
            Success message
        """
        params = {"group_id": group_id}
        if name is not None:
            params["name"] = name
        if topic is not None:
            params["topic"] = topic
        return await self.call("group_update", params)

    async def contact_check(self, phones: list) -> list:
        """
        Check if phone numbers are registered on WhatsApp.

        Args:
            phones: List of phone numbers (without + prefix)

        Returns:
            List of dicts with query, jid, is_registered, is_business, business_name
        """
        return await self.call("contact_check", {"phones": phones})

    async def contact_profile_pic(self, jid: str, preview: bool = False) -> dict:
        """
        Get profile picture for a user or group.

        Args:
            jid: User or group JID (e.g., '1234567890@s.whatsapp.net')
            preview: Get smaller preview image instead of full size

        Returns:
            Dict with exists, url, id, data (base64 if available)
        """
        return await self.call("contact_profile_pic", {"jid": jid, "preview": preview})

    async def typing(self, jid: str, state: str = "composing", media: str = "") -> dict:
        """
        Send typing indicator to a chat.

        Args:
            jid: Chat JID (individual or group)
            state: 'composing' (typing) or 'paused' (stopped typing)
            media: '' for text typing, 'audio' for recording voice

        Returns:
            Success message
        """
        params = {"jid": jid, "state": state}
        if media:
            params["media"] = media
        return await self.call("typing", params)

    async def presence(self, status: str) -> dict:
        """
        Set online/offline presence status.

        Args:
            status: 'available' (online) or 'unavailable' (offline)

        Returns:
            Success message
        """
        return await self.call("presence", {"status": status})

    async def mark_read(self, message_ids: list, chat_jid: str, sender_jid: str = None) -> dict:
        """
        Mark messages as read.

        Args:
            message_ids: List of message IDs to mark as read
            chat_jid: Chat JID where messages are from
            sender_jid: Sender JID (required for group messages)

        Returns:
            Success message
        """
        params = {"message_ids": message_ids, "chat_jid": chat_jid}
        if sender_jid:
            params["sender_jid"] = sender_jid
        return await self.call("mark_read", params)

    async def group_participants_add(self, group_id: str, participants: list) -> dict:
        """
        Add participants to a group.

        Args:
            group_id: Group JID (e.g., '123456789@g.us')
            participants: List of phone numbers or JIDs to add

        Returns:
            Dict with group_id, action, results (list with success/error per participant),
            added count, and failed count
        """
        return await self.call("group_participants_add", {
            "group_id": group_id,
            "participants": participants
        })

    async def group_participants_remove(self, group_id: str, participants: list) -> dict:
        """
        Remove participants from a group.

        Args:
            group_id: Group JID (e.g., '123456789@g.us')
            participants: List of phone numbers or JIDs to remove

        Returns:
            Dict with group_id, action, results (list with success/error per participant),
            removed count, and failed count
        """
        return await self.call("group_participants_remove", {
            "group_id": group_id,
            "participants": participants
        })

    async def group_invite_link(self, group_id: str) -> dict:
        """
        Get the invite link for a group.

        Args:
            group_id: Group JID (e.g., '123456789@g.us')

        Returns:
            Dict with group_id, invite_link
        """
        return await self.call("group_invite_link", {"group_id": group_id})

    async def group_revoke_invite(self, group_id: str) -> dict:
        """
        Revoke and regenerate the group invite link.

        Args:
            group_id: Group JID (e.g., '123456789@g.us')

        Returns:
            Dict with group_id, invite_link (new), revoked=true
        """
        return await self.call("group_revoke_invite", {"group_id": group_id})

    # ========================================================================
    # Rate Limiting Methods (Anti-Ban Protection)
    # ========================================================================

    async def rate_limit_get(self) -> dict:
        """
        Get current rate limit configuration and statistics.

        Returns:
            Dict with 'config' (RateLimitConfig) and 'stats' (RateLimitStats)
        """
        return await self.call("rate_limit_get")

    async def rate_limit_set(self, **config) -> dict:
        """
        Update rate limit configuration dynamically.

        Args:
            enabled: Enable/disable rate limiting
            min_delay_ms: Minimum delay between messages (ms, default: 3000)
            max_delay_ms: Maximum delay for randomization (ms, default: 8000)
            typing_delay_ms: Typing indicator duration (ms, default: 2000)
            link_extra_delay_ms: Extra delay for messages with links (ms, default: 5000)
            max_messages_per_minute: Per-minute message limit (default: 10)
            max_messages_per_hour: Per-hour message limit (default: 60)
            max_new_contacts_per_day: Daily new contact limit (default: 20)
            simulate_typing: Send typing indicator before messages (default: true)
            randomize_delays: Add random variance to delays (default: true)
            pause_on_low_response: Pause if response rate < threshold (default: false)
            response_rate_threshold: Min response rate 0.0-1.0 (default: 0.3)

        Returns:
            Dict with 'message' and updated 'config'
        """
        return await self.call("rate_limit_set", config)

    async def rate_limit_stats(self) -> dict:
        """
        Get current rate limiting statistics.

        Returns:
            Dict with messages_sent_last_minute, messages_sent_last_hour,
            messages_sent_today, new_contacts_today, response_rate,
            is_paused, pause_reason, last_message_time, next_allowed_time
        """
        return await self.call("rate_limit_stats")

    async def rate_limit_unpause(self) -> dict:
        """
        Unpause rate limiting after it was paused due to low response rate.

        Returns:
            Dict with 'message' and current 'stats'
        """
        return await self.call("rate_limit_unpause")

    # ========================================================================
    # Chat History Methods
    # ========================================================================

    async def chat_history(self, **kwargs) -> list:
        """
        Get stored message history for a chat.

        Args:
            phone: Phone number (or use chat_id/group_id)
            chat_id: Chat JID
            group_id: Group JID
            limit: Max messages to return (default: 50)
            offset: Skip first N messages
            sender_phone: Filter by sender
            text_only: Only return text messages

        Returns:
            List of message dicts
        """
        return await self.call("chat_history", kwargs)

    # ========================================================================
    # Contacts Methods
    # ========================================================================

    async def contacts(self, query: str = None) -> list:
        """
        List all contacts with saved names.

        Args:
            query: Optional search filter

        Returns:
            List of contact dicts
        """
        params = {}
        if query is not None:
            params["query"] = query
        return await self.call("contacts", params)

    async def contact_info(self, phone: str) -> dict:
        """
        Get full contact info.

        Args:
            phone: Phone number

        Returns:
            Dict with name, business status, profile pic, etc.
        """
        return await self.call("contact_info", {"phone": phone})

    # ========================================================================
    # Newsletter (Channel) Methods
    # ========================================================================

    async def newsletters(self, refresh: bool = False) -> list:
        """
        List subscribed channels (cached 24h).

        Args:
            refresh: Force refresh from WhatsApp API

        Returns:
            List of newsletter info dicts
        """
        params = {}
        if refresh:
            params["refresh"] = True
        return await self.call("newsletters", params)

    async def newsletter_info(self, jid: str = None, invite: str = None, refresh: bool = False) -> dict:
        """
        Get channel details by JID or invite link.

        Args:
            jid: Channel JID (e.g., '123456789@newsletter')
            invite: Invite link (e.g., 'https://whatsapp.com/channel/...')
            refresh: Force refresh from API

        Returns:
            Newsletter info dict
        """
        params = {}
        if jid:
            params["jid"] = jid
        if invite:
            params["invite"] = invite
        if refresh:
            params["refresh"] = True
        return await self.call("newsletter_info", params)

    async def newsletter_create(self, name: str, description: str = None, picture: str = None) -> dict:
        """
        Create a new channel.

        Args:
            name: Channel name
            description: Channel description (optional)
            picture: Base64-encoded picture (optional)

        Returns:
            Newsletter info dict for created channel
        """
        params = {"name": name}
        if description:
            params["description"] = description
        if picture:
            params["picture"] = picture
        return await self.call("newsletter_create", params)

    async def newsletter_follow(self, jid: str) -> dict:
        """
        Subscribe to a channel.

        Args:
            jid: Channel JID
        """
        return await self.call("newsletter_follow", {"jid": jid})

    async def newsletter_unfollow(self, jid: str) -> dict:
        """
        Unsubscribe from a channel.

        Args:
            jid: Channel JID
        """
        return await self.call("newsletter_unfollow", {"jid": jid})

    async def newsletter_mute(self, jid: str, mute: bool = True) -> dict:
        """
        Mute or unmute a channel.

        Args:
            jid: Channel JID
            mute: True to mute, False to unmute
        """
        return await self.call("newsletter_mute", {"jid": jid, "mute": mute})

    async def newsletter_messages(self, jid: str, count: int = 10, before: int = None) -> list:
        """
        Get messages from a channel.

        Args:
            jid: Channel JID
            count: Number of messages to fetch (default: 10)
            before: Fetch messages before this server ID (for pagination)

        Returns:
            List of newsletter message dicts
        """
        params = {"jid": jid, "count": count}
        if before is not None:
            params["before"] = before
        return await self.call("newsletter_messages", params)

    async def newsletter_send(self, group_id: str, type: str = "text", message: str = None, media_data: dict = None) -> dict:
        """
        Send a message to a channel (admin only).

        Args:
            group_id: Channel JID (e.g., '123456789@newsletter')
            type: Message type (text, image, video, etc.)
            message: Text content
            media_data: Media content dict with data, mime_type, caption

        Returns:
            Success message
        """
        params = {"group_id": group_id, "type": type}
        if message:
            params["message"] = message
        if media_data:
            params["media_data"] = media_data
        return await self.call("newsletter_send", params)

    async def newsletter_mark_viewed(self, jid: str, server_ids: list) -> dict:
        """
        Mark channel messages as viewed.

        Args:
            jid: Channel JID
            server_ids: List of message server IDs to mark as viewed
        """
        return await self.call("newsletter_mark_viewed", {"jid": jid, "server_ids": server_ids})

    async def newsletter_react(self, jid: str, server_id: int, reaction: str) -> dict:
        """
        React to a channel message.

        Args:
            jid: Channel JID
            server_id: Message server ID
            reaction: Reaction emoji
        """
        return await self.call("newsletter_react", {"jid": jid, "server_id": server_id, "reaction": reaction})

    async def newsletter_live_updates(self, jid: str) -> dict:
        """
        Subscribe to live view/reaction updates for a channel.

        Args:
            jid: Channel JID

        Returns:
            Dict with duration (seconds) of subscription
        """
        return await self.call("newsletter_live_updates", {"jid": jid})

    async def newsletter_stats(self, jid: str = None, invite: str = None, count: int = 20) -> dict:
        """
        Get channel statistics (views, reactions, aggregates).

        Args:
            jid: Channel JID
            invite: Invite link (alternative to JID)
            count: Number of recent messages to analyze (default: 20)

        Returns:
            Dict with subscriber_count, total_views, avg_views_per_message,
            total_reactions, top_reactions, per-message breakdowns
        """
        params = {"count": count}
        if jid:
            params["jid"] = jid
        if invite:
            params["invite"] = invite
        return await self.call("newsletter_stats", params)
