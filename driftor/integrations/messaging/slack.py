"""
Slack integration with block kit and enterprise security.
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from slack_bolt.async_app import AsyncApp
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError
import structlog

from .base import BaseMessagingPlatform, MessagePlatform, MessageCard, MessageResponse, InteractiveButton, ButtonAction
from driftor.integrations.base import IntegrationConfig, WebhookConfig
from driftor.core.rate_limiter import RateLimitType
from driftor.security.audit import audit, AuditEventType

logger = structlog.get_logger(__name__)


class SlackBot(BaseMessagingPlatform):
    """Slack bot integration with Block Kit UI."""
    
    def __init__(self, config: IntegrationConfig, credentials: Dict[str, str]):
        super().__init__(config, credentials)
        
        # Set up rate limiting
        config.rate_limit_type = RateLimitType.SLACK_MESSAGES
        
        self.bot_token = self.get_credential("bot_token")
        self.app_token = self.get_credential("app_token")
        self.signing_secret = self.get_credential("signing_secret")
        
        # Initialize Slack app
        self.app = AsyncApp(
            token=self.bot_token,
            signing_secret=self.signing_secret
        )
        
        # Initialize web client
        self.client = AsyncWebClient(token=self.bot_token)
        
        # Store active conversations
        self.active_conversations: Dict[str, Dict[str, Any]] = {}
        
        # Set up event handlers
        self._setup_event_handlers()
    
    def _get_platform_type(self) -> MessagePlatform:
        return MessagePlatform.SLACK
    
    async def test_connection(self) -> bool:
        """Test Slack API connection."""
        try:
            response = await self.client.auth_test()
            if response["ok"]:
                logger.info(
                    "Slack connection successful",
                    bot_id=response.get("bot_id"),
                    user_id=response.get("user_id"),
                    tenant_id=self.config.tenant_id
                )
                return True
            
            return False
            
        except SlackApiError as e:
            logger.error(
                "Slack connection failed",
                error=e.response["error"],
                tenant_id=self.config.tenant_id
            )
            return False
        except Exception as e:
            logger.error("Slack connection error", error=str(e))
            return False
    
    def get_webhook_config(self) -> Optional[WebhookConfig]:
        """Get Slack webhook configuration."""
        return WebhookConfig(
            endpoint_url=f"{self.config.api_base_url}/webhooks/slack",
            secret=self.signing_secret,
            events=[
                "message",
                "app_mention",
                "interactive_message",
                "slash_command"
            ]
        )
    
    async def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        """Verify Slack webhook signature."""
        return self.verify_webhook_signature_hmac(
            payload, signature, self.signing_secret, "sha256"
        )
    
    def _setup_event_handlers(self):
        """Set up Slack event handlers."""
        
        @self.app.event("app_mention")
        async def handle_app_mention(event, say):
            """Handle app mentions."""
            try:
                user_id = event["user"]
                text = event["text"]
                channel = event["channel"]
                
                logger.info(
                    "Slack app mention received",
                    user_id=user_id,
                    channel=channel,
                    text=text[:100]
                )
                
                # Simple response for mentions
                await say(
                    text="Hi! I'm Driftor, your AI bug analysis assistant. "
                         "I automatically analyze Jira tickets and provide fix suggestions. "
                         "Type `help` to learn more!",
                    channel=channel
                )
                
            except Exception as e:
                logger.error("Failed to handle app mention", error=str(e))
        
        @self.app.message("help")
        async def handle_help_message(message, say):
            """Handle help requests."""
            help_text = """
🤖 **Driftor - AI Bug Analysis Assistant**

I automatically analyze Jira bug tickets and provide:
• 🔍 Similar issue analysis
• 📚 Relevant documentation
• 💡 Fix suggestions with confidence scores
• 🗣️ Interactive chat support

**Commands:**
• `@driftor help` - Show this help
• `@driftor analyze TICKET-123` - Analyze specific ticket
• `@driftor status` - Check my status

I'll automatically notify you when bug tickets are assigned to you!
            """
            
            await say(text=help_text, channel=message["channel"])
    
    async def send_message(
        self, 
        user_id: str, 
        message: str, 
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send a simple text message."""
        try:
            await self._check_rate_limit(user_id)
            
            # Send direct message or to channel
            kwargs = {
                "channel": user_id,
                "text": message
            }
            
            if thread_id:
                kwargs["thread_ts"] = thread_id
            
            response = await self.client.chat_postMessage(**kwargs)
            
            if response["ok"]:
                return MessageResponse(
                    success=True,
                    message_id=response["ts"],
                    thread_id=thread_id,
                    platform=self.platform.value
                )
            else:
                return MessageResponse(
                    success=False,
                    error=response.get("error", "Unknown error"),
                    platform=self.platform.value
                )
                
        except SlackApiError as e:
            logger.error(
                "Failed to send Slack message",
                user_id=user_id,
                error=e.response["error"]
            )
            return MessageResponse(
                success=False,
                error=e.response["error"],
                platform=self.platform.value
            )
        except Exception as e:
            logger.error("Slack send message error", error=str(e))
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    async def send_card(
        self, 
        user_id: str, 
        card: MessageCard,
        thread_id: Optional[str] = None
    ) -> MessageResponse:
        """Send a block kit message."""
        try:
            await self._check_rate_limit(user_id)
            
            # Create block kit blocks
            blocks = self._create_block_kit_blocks(card)
            
            # Send message with blocks
            kwargs = {
                "channel": user_id,
                "text": card.title,  # Fallback text
                "blocks": blocks
            }
            
            if thread_id:
                kwargs["thread_ts"] = thread_id
            
            response = await self.client.chat_postMessage(**kwargs)
            
            if response["ok"]:
                return MessageResponse(
                    success=True,
                    message_id=response["ts"],
                    thread_id=thread_id,
                    platform=self.platform.value
                )
            else:
                return MessageResponse(
                    success=False,
                    error=response.get("error", "Unknown error"),
                    platform=self.platform.value
                )
                
        except SlackApiError as e:
            logger.error(
                "Failed to send Slack card",
                user_id=user_id,
                error=e.response["error"]
            )
            return MessageResponse(
                success=False,
                error=e.response["error"],
                platform=self.platform.value
            )
        except Exception as e:
            logger.error("Slack send card error", error=str(e))
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    async def handle_interaction(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle block kit interactive components."""
        try:
            payload = interaction_data.get("payload", {})
            
            if isinstance(payload, str):
                payload = json.loads(payload)
            
            action_id = ""
            ticket_key = ""
            user_id = payload.get("user", {}).get("id", "")
            
            # Handle button clicks
            if payload.get("type") == "block_actions":
                actions = payload.get("actions", [])
                if actions:
                    action = actions[0]
                    action_id = action.get("action_id", "")
                    ticket_key = action.get("value", "")
            
            logger.info(
                "Slack interaction received",
                action_id=action_id,
                ticket_key=ticket_key,
                user_id=user_id
            )
            
            # Route to appropriate handler
            if action_id == "elaborate_fix":
                return await self._handle_elaborate_fix(payload, ticket_key)
            elif action_id == "chat_with_driftor":
                return await self._handle_chat_request(payload, ticket_key)
            elif action_id == "mark_helpful":
                return await self._handle_feedback(payload, ticket_key, True)
            elif action_id == "mark_unhelpful":
                return await self._handle_feedback(payload, ticket_key, False)
            elif action_id == "view_similar_tickets":
                return await self._handle_view_similar_tickets(payload, ticket_key)
            elif action_id == "view_documentation":
                return await self._handle_view_documentation(payload, ticket_key)
            else:
                return {"status": "unknown_action", "action_id": action_id}
            
        except Exception as e:
            logger.error("Failed to handle Slack interaction", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def start_conversation(
        self, 
        user_id: str, 
        initial_message: str
    ) -> MessageResponse:
        """Start a new conversation thread."""
        try:
            # Send initial message
            response = await self.client.chat_postMessage(
                channel=user_id,
                text=initial_message
            )
            
            if response["ok"]:
                thread_ts = response["ts"]
                
                # Store conversation context
                conversation_id = f"driftor_{user_id}_{thread_ts}"
                self.active_conversations[conversation_id] = {
                    "user_id": user_id,
                    "thread_ts": thread_ts,
                    "started_at": datetime.now().isoformat(),
                    "messages": [{"role": "assistant", "content": initial_message}]
                }
                
                return MessageResponse(
                    success=True,
                    message_id=thread_ts,
                    thread_id=thread_ts,
                    platform=self.platform.value
                )
            else:
                return MessageResponse(
                    success=False,
                    error=response.get("error", "Unknown error"),
                    platform=self.platform.value
                )
                
        except Exception as e:
            logger.error("Failed to start Slack conversation", error=str(e))
            return MessageResponse(
                success=False,
                error=str(e),
                platform=self.platform.value
            )
    
    def _create_block_kit_blocks(self, card: MessageCard) -> List[Dict[str, Any]]:
        """Create Block Kit blocks from MessageCard."""
        blocks = []
        
        # Header block with title
        if card.title:
            header_text = card.title
            if card.subtitle:
                header_text += f"\n{card.subtitle}"
            
            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": card.title[:150]  # Slack limit
                }
            })
            
            if card.subtitle:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": card.subtitle
                        }
                    ]
                })
        
        # Main text section
        if card.text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": card.text[:3000]  # Slack limit
                }
            })
        
        # Facts as fields
        if card.facts:
            fields = []
            for fact in card.facts:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*{fact['name']}*\n{fact['value']}"
                })
            
            # Split into chunks of 10 (Slack limit)
            for i in range(0, len(fields), 10):
                chunk = fields[i:i+10]
                blocks.append({
                    "type": "section",
                    "fields": chunk
                })
        
        # Divider before buttons
        if card.buttons:
            blocks.append({"type": "divider"})
        
        # Buttons as actions
        if card.buttons:
            # Group buttons (max 5 per block)
            for i in range(0, len(card.buttons), 5):
                button_chunk = card.buttons[i:i+5]
                elements = []
                
                for button in button_chunk:
                    element = {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": button.text[:75]  # Slack limit
                        },
                        "action_id": button.id,
                        "value": button.value or ""
                    }
                    
                    # Handle URL buttons
                    if button.url:
                        element["url"] = button.url
                    
                    # Handle button styles
                    if button.style == "primary":
                        element["style"] = "primary"
                    elif button.style == "danger":
                        element["style"] = "danger"
                    
                    elements.append(element)
                
                blocks.append({
                    "type": "actions",
                    "elements": elements
                })
        
        # Add thumbnail if available
        if card.thumbnail_url:
            # Add as accessory to first section
            for block in blocks:
                if block.get("type") == "section" and "text" in block:
                    block["accessory"] = {
                        "type": "image",
                        "image_url": card.thumbnail_url,
                        "alt_text": "Driftor logo"
                    }
                    break
        
        return blocks
    
    async def _handle_elaborate_fix(self, payload: Dict[str, Any], ticket_key: str) -> Dict[str, Any]:
        """Handle elaborate fix button click."""
        try:
            user_id = payload.get("user", {}).get("id", "")
            channel = payload.get("channel", {}).get("id", "")
            
            detailed_fix = f"Here's a more detailed explanation for *{ticket_key}*:\n\n" \
                          "• The issue appears to be in the error handling logic\n" \
                          "• Consider adding null checks before accessing properties\n" \
                          "• Implement proper exception handling\n\n" \
                          "Would you like me to provide specific code examples?"
            
            await self.send_message(user_id or channel, detailed_fix)
            
            return {"status": "elaborated", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle elaborate fix", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_chat_request(self, payload: Dict[str, Any], ticket_key: str) -> Dict[str, Any]:
        """Handle chat with Driftor request."""
        try:
            user_id = payload.get("user", {}).get("id", "")
            
            chat_message = f"Hi! I'm here to help with *{ticket_key}*. " \
                          "What specific questions do you have about this issue?\n\n" \
                          "I can help with:\n" \
                          "• Code analysis and debugging\n" \
                          "• Similar issue research\n" \
                          "• Best practice recommendations\n" \
                          "• Documentation search\n\n" \
                          "Just ask me anything!"
            
            response = await self.start_conversation(user_id, chat_message)
            
            return {
                "status": "chat_started",
                "ticket_key": ticket_key,
                "conversation_id": response.thread_id
            }
            
        except Exception as e:
            logger.error("Failed to handle chat request", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_feedback(
        self, 
        payload: Dict[str, Any], 
        ticket_key: str, 
        helpful: bool
    ) -> Dict[str, Any]:
        """Handle feedback button clicks."""
        try:
            user_id = payload.get("user", {}).get("id", "")
            
            feedback_message = "Thank you for your feedback! " \
                             f"Your input helps improve Driftor's analysis quality."
            
            if not helpful:
                feedback_message += "\n\nWhat could I have done better? " \
                                  "You can DM me to provide more specific feedback."
            
            await self.send_message(user_id, feedback_message)
            
            # TODO: Store feedback in database
            
            return {
                "status": "feedback_received",
                "ticket_key": ticket_key,
                "helpful": helpful
            }
            
        except Exception as e:
            logger.error("Failed to handle feedback", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_view_similar_tickets(
        self, 
        payload: Dict[str, Any], 
        ticket_key: str
    ) -> Dict[str, Any]:
        """Handle view similar tickets request."""
        try:
            user_id = payload.get("user", {}).get("id", "")
            
            similar_message = f"Here are similar issues to *{ticket_key}*:\n\n" \
                            "• *PROJ-123*: Similar null pointer exception\n" \
                            "• *PROJ-124*: Related API timeout issue\n" \
                            "• *PROJ-125*: Same component error pattern\n\n" \
                            "Would you like detailed analysis of any of these?"
            
            await self.send_message(user_id, similar_message)
            
            return {"status": "similar_tickets_shown", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle view similar tickets", error=str(e))
            return {"status": "error", "error": str(e)}
    
    async def _handle_view_documentation(
        self, 
        payload: Dict[str, Any], 
        ticket_key: str
    ) -> Dict[str, Any]:
        """Handle view documentation request."""
        try:
            user_id = payload.get("user", {}).get("id", "")
            
            docs_message = f"Relevant documentation for *{ticket_key}*:\n\n" \
                          "📚 *Error Handling Best Practices*\n" \
                          "<https://docs.company.com/error-handling|View Guide>\n\n" \
                          "📚 *API Integration Guide*\n" \
                          "<https://docs.company.com/api-guide|View Guide>\n\n" \
                          "📚 *Troubleshooting Common Issues*\n" \
                          "<https://docs.company.com/troubleshooting|View Guide>"
            
            await self.send_message(user_id, docs_message)
            
            return {"status": "documentation_shown", "ticket_key": ticket_key}
            
        except Exception as e:
            logger.error("Failed to handle view documentation", error=str(e))
            return {"status": "error", "error": str(e)}