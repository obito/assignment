import asyncio
import json
import logging
from typing import Any, Dict, List
from dotenv import load_dotenv

from livekit import api
from livekit.agents import (
    AgentSession,
    Agent,
    ErrorEvent,
    MetricsCollectedEvent,
    RoomInputOptions,
    metrics,
    JobContext,
    WorkerOptions,
    function_tool,
    RunContext,
)
from livekit.plugins import silero, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from livekit.agents.telemetry import set_tracer_provider

# Knowledge base imports
import chromadb


# Setup LangFuse OpenTelemetry
def setup_langfuse(
    host: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    metadata: dict | None = None,
):
    try:
        import base64
        import os
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        public_key = public_key or os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = secret_key or os.getenv("LANGFUSE_SECRET_KEY")
        host = host or os.getenv("LANGFUSE_HOST")

        if not public_key or not secret_key or not host:
            logger.warning("LangFuse credentials not set, skipping LangFuse setup")
            return

        langfuse_auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = (
            f"{host.rstrip('/')}/api/public/otel"
        )
        os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = (
            f"Authorization=Basic {langfuse_auth}"
        )

        trace_provider = TracerProvider()
        trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        set_tracer_provider(trace_provider)
        logger.info("LangFuse OpenTelemetry configured successfully")
        return trace_provider
    except ImportError:
        logger.warning("OpenTelemetry packages not installed, skipping telemetry setup")
        return None
    except Exception as e:
        logger.warning(f"Failed to setup LangFuse: {e}")
        return None


load_dotenv(".env.local")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Outbound trunk configuration
OUTBOUND_TRUNK_ID = "ST_bK3p7CF6Pfp4"


class KnowledgeBase:
    def __init__(self):
        """Initialize ChromaDB knowledge base with sample data."""
        self.client = chromadb.Client()

        # Create or get collection
        self.collection = self.client.get_or_create_collection(
            name="voice_agent_kb", metadata={"hnsw:space": "cosine"}
        )

        # Initialize with sample data if empty
        if self.collection.count() == 0:
            self._initialize_sample_data()

    def _initialize_sample_data(self):
        """Initialize the knowledge base with sample data."""
        sample_data = [
            {
                "id": "refund_policy",
                "text": "Our refund policy allows full refunds within 30 days of purchase. Contact customer support at support@company.com or call 1-800-HELP for assistance.",
                "metadata": {"category": "policy", "topic": "refund"},
            },
            {
                "id": "objection_price",
                "text": "I understand price is a concern. Let me explain the value you get: 24/7 support, premium features, and a 30-day money-back guarantee. Many customers save more than the cost in the first month.",
                "metadata": {"category": "objection", "topic": "price"},
            },
            {
                "id": "objection_time",
                "text": "I know you're busy, but this will actually save you time. Most customers see results within the first week. Would you like to start with a free trial to see for yourself?",
                "metadata": {"category": "objection", "topic": "time"},
            },
            {
                "id": "objection_trust",
                "text": "I understand your concern about trust. We're a company with 10+ years in business, thousands of satisfied customers, and we're backed by industry leaders. Would you like to see some customer testimonials?",
                "metadata": {"category": "objection", "topic": "trust"},
            },
            {
                "id": "contact_info",
                "text": "You can reach us at support@company.com, call 1-800-HELP, or visit our website at www.company.com. Our support team is available 24/7.",
                "metadata": {"category": "contact", "topic": "support"},
            },
            {
                "id": "features",
                "text": "Our main features include: automated workflows, real-time analytics, team collaboration tools, mobile app access, and enterprise-grade security. All features come with our standard plan.",
                "metadata": {"category": "product", "topic": "features"},
            },
        ]

        # Add documents to collection
        self.collection.add(
            documents=[item["text"] for item in sample_data],
            metadatas=[item["metadata"] for item in sample_data],
            ids=[item["id"] for item in sample_data],
        )

        logger.info(f"Initialized knowledge base with {len(sample_data)} documents")

    def search(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Search the knowledge base for relevant information."""
        try:
            results = self.collection.query(query_texts=[query], n_results=n_results)

            # Format results
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append(
                        {
                            "text": doc,
                            "metadata": results["metadatas"][0][i]
                            if results["metadatas"]
                            else {},
                            "distance": results["distances"][0][i]
                            if results["distances"]
                            else 0,
                        }
                    )

            return formatted_results
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor.
            Keep responses under 2 sentences for faster processing.
            When users ask about policies, objections, or need specific information, use the knowledge base search function.""",
        )
        # Latency tracking
        self.latency_start_time = None
        self.stt_start_time = None
        self.llm_start_time = None
        self.tts_start_time = None

        # Initialize knowledge base
        self.knowledge_base = KnowledgeBase()

    @function_tool
    async def search_knowledge_base(
        self,
        context: RunContext,
        query: str,
    ) -> Dict[str, Any]:
        """Search the knowledge base for relevant information about policies, objections, or general questions.
        For example, if the user asks about the refund policy, you can use this function to search the knowledge base for the relevant information.

        Args:
            query: The search query to find relevant information in the knowledge base.
        """
        try:
            logger.info(f"Searching knowledge base for: {query}")
            results = self.knowledge_base.search(query, n_results=2)

            if results:
                # Return the most relevant result
                best_result = results[0]
                return {
                    "found": True,
                    "information": best_result["text"],
                    "category": best_result["metadata"].get("category", "general"),
                    "topic": best_result["metadata"].get("topic", "unknown"),
                    "relevance_score": 1
                    - best_result["distance"],  # Convert distance to relevance
                }
            else:
                return {
                    "found": False,
                    "information": "No relevant information found in the knowledge base.",
                    "category": "none",
                    "topic": "none",
                    "relevance_score": 0.0,
                }
        except Exception as e:
            logger.error(f"Error in knowledge base search: {e}")
            return {
                "found": False,
                "information": "Sorry, I encountered an error while searching for information.",
                "category": "error",
                "topic": "error",
                "relevance_score": 0.0,
            }


async def entrypoint(ctx: JobContext):
    # Setup LangFuse OpenTelemetry with metadata
    trace_provider = setup_langfuse(
        metadata={
            "langfuse.session.id": ctx.room.name,
        }
    )

    # Add shutdown callback to flush traces
    async def flush_trace():
        if trace_provider:
            trace_provider.force_flush()

    ctx.add_shutdown_callback(flush_trace)
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()

    participant_identity = phone_number = None

    try:
        dial_info = json.loads(ctx.job.metadata)
        participant_identity = phone_number = dial_info.get("phone_number")
        if not participant_identity:
            logger.warning(f"No phone_number found in metadata: {ctx.job.metadata}")
    except Exception as e:
        logger.warning(
            f"Could not parse metadata or missing phone_number: {ctx.job.metadata} ({e})"
        )
        participant_identity = phone_number = None

    try:
        session = AgentSession(
            stt="assemblyai/universal-streaming:en",
            llm="openai/gpt-4.1-mini",
            tts="cartesia/sonic-2:9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
            turn_detection=MultilingualModel(),
            vad=silero.VAD.load(),
            preemptive_generation=True,
        )

        usage_collector = metrics.UsageCollector()

        @session.on("metrics_collected")
        def _on_metrics_collected(ev: MetricsCollectedEvent):
            metrics.log_metrics(ev.metrics)
            usage_collector.collect(ev.metrics)

        async def log_usage():
            summary = usage_collector.get_summary()
            logger.info(f"Usage: {summary}")

        @session.on("error")
        def on_error(ev: ErrorEvent):
            if ev.error.recoverable:
                return

            logger.info(f"session is closing due to unrecoverable error {ev.error}")

            session.say(
                "I'm having trouble connecting right now. Let me transfer your call.",
                allow_interruptions=False,
            )

        # Create assistant instance
        assistant = Assistant()
        assistant.ctx = ctx  # Store context for outbound calling

        # Start the session first
        logger.info("About to start session")
        session_started = asyncio.create_task(
            session.start(
                room=ctx.room,
                agent=assistant,
                room_input_options=RoomInputOptions(
                    noise_cancellation=noise_cancellation.BVCTelephony(),
                ),
            )
        )

        if phone_number:
            try:
                await ctx.api.sip.create_sip_participant(
                    api.CreateSIPParticipantRequest(
                        room_name=ctx.room.name,
                        sip_trunk_id=OUTBOUND_TRUNK_ID,
                        sip_call_to=phone_number,
                        participant_identity=participant_identity,
                        wait_until_answered=True,
                    )
                )

                # Wait for the session to start and participant to join
                await session_started
                participant = await ctx.wait_for_participant(
                    identity=participant_identity
                )
                logger.info(f"participant joined: {participant.identity}")

            except api.TwirpError as e:
                logger.error(
                    f"error creating SIP participant: {e.message}, "
                    f"SIP status: {e.metadata.get('sip_status_code')} "
                    f"{e.metadata.get('sip_status')}"
                )
                ctx.shutdown()

    except Exception as e:
        logger.error(f"Error in entrypoint: {e}")
        raise


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Run the agent using WorkerOptions pattern
    from livekit.agents.cli import cli

    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, agent_name="outbound-caller"))
