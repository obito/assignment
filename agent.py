import asyncio
import logging
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions, llm
from livekit.plugins import noise_cancellation, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from metrics import metrics

load_dotenv(".env.local")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scripted_reply(user_input: str) -> str:
    # Exemple très simple
    if "refund" in user_input.lower():
        return "Our refund policy is 30 days no questions asked."
    elif "hello" in user_input.lower():
        return "Hello! How can I help you today?"
    else:
        return None  # None = pas de règle, fallback LLM
    
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.""",
        )
        self.call_id = None
    
    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # Mark LLM processing start
        if self.call_id:
            metrics.mark_llm_start(self.call_id)
        
        try:
            # Scripted dialog check
            scripted = scripted_reply(new_message.text_content)
            if scripted:
                # Mark TTS start for scripted response
                if self.call_id:
                    metrics.mark_tts_start(self.call_id)
                
                # Envoyer direct une réponse TTS, sans passer par LLM
                await self.session.say(scripted)
                
                # Mark TTS end and LLM end (no LLM processing for scripted)
                if self.call_id:
                    metrics.mark_llm_end(self.call_id)
                    metrics.mark_tts_end(self.call_id)
                    metrics.mark_audio_delivered(self.call_id)
                return

            # Sinon, laisser la pipeline par défaut (LLM)
            await super().on_user_turn_completed(turn_ctx, new_message)
            
            # Mark LLM end
            if self.call_id:
                metrics.mark_llm_end(self.call_id)
                
        except Exception as e:
            logger.error(f"Error in user turn processing: {e}")
            if self.call_id:
                metrics.record_failed_call_setup()
            raise
    
    async def on_tts_started(self):
        """Called when TTS processing starts."""
        if self.call_id:
            metrics.mark_tts_start(self.call_id)
    
    async def on_tts_completed(self):
        """Called when TTS processing completes."""
        if self.call_id:
            metrics.mark_tts_end(self.call_id)
            metrics.mark_audio_delivered(self.call_id)
    
    async def on_stt_started(self):
        """Called when STT processing starts."""
        if self.call_id:
            metrics.mark_stt_start(self.call_id)
    
    async def on_stt_completed(self):
        """Called when STT processing completes."""
        if self.call_id:
            metrics.mark_stt_end(self.call_id)


async def entrypoint(ctx: agents.JobContext):
    # Generate unique call ID
    call_id = f"call_{ctx.room.name}_{int(asyncio.get_event_loop().time())}"
    
    # Start metrics tracking for this call
    metrics.start_call(call_id)
    
    try:
        session = AgentSession(
            stt="assemblyai/universal-streaming:fr",
            llm="openai/gpt-4.1-mini",
            tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            vad=silero.VAD.load(),
            turn_detection=MultilingualModel(),
        )

        # Create assistant instance and set call ID
        assistant = Assistant()
        assistant.call_id = call_id

        await session.start(
            room=ctx.room,
            agent=assistant,
            room_input_options=RoomInputOptions(
                # For telephony applications, use `BVCTelephony` instead for best results
                noise_cancellation=noise_cancellation.BVC(), 
            ),
        )

        await session.generate_reply(
            instructions="Greet the user and offer your assistance."
        )
        
        logger.info(f"Call {call_id} started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start call {call_id}: {e}")
        metrics.record_failed_call_setup()
        raise
    finally:
        # End call tracking when room disconnects
        try:
            # Simulate audio quality metrics (in real implementation, these would come from audio analysis)
            mos_score = 4.2  # Simulated MOS score
            jitter_ms = 15.0  # Simulated jitter
            packet_loss_rate = 0.1  # Simulated packet loss rate
            
            metrics.end_call(call_id, mos_score, jitter_ms, packet_loss_rate)
            logger.info(f"Call {call_id} ended")
        except Exception as e:
            logger.error(f"Error ending call metrics for {call_id}: {e}")


async def start_monitoring():
    """Start background system monitoring."""
    await metrics.start_system_monitoring()

if __name__ == "__main__":
    # Start system monitoring in background
    asyncio.create_task(start_monitoring())
    
    # Start the agent
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))