"""
Metrics collection module for LiveKit voice agent.
Tracks end-to-end latency, MOS, jitter, packet loss, and other performance metrics.
"""

import time
import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from prometheus_client import Counter, Histogram, Gauge, Summary, start_http_server
import psutil
import logging

logger = logging.getLogger(__name__)

@dataclass
class LatencyMetrics:
    """Container for latency measurements throughout the pipeline."""
    speech_start: float = 0.0
    stt_start: float = 0.0
    stt_end: float = 0.0
    llm_start: float = 0.0
    llm_end: float = 0.0
    tts_start: float = 0.0
    tts_end: float = 0.0
    audio_delivered: float = 0.0
    
    def get_stt_latency(self) -> float:
        return (self.stt_end - self.stt_start) * 1000  # Convert to ms
    
    def get_llm_latency(self) -> float:
        return (self.llm_end - self.llm_start) * 1000  # Convert to ms
    
    def get_tts_latency(self) -> float:
        return (self.tts_end - self.tts_start) * 1000  # Convert to ms
    
    def get_end_to_end_latency(self) -> float:
        return (self.audio_delivered - self.speech_start) * 1000  # Convert to ms

class VoiceAgentMetrics:
    """Comprehensive metrics collection for voice agent performance."""
    
    def __init__(self, port: int = 8000):
        self.port = port
        self.active_calls: Dict[str, LatencyMetrics] = {}
        self.call_history: List[LatencyMetrics] = []
        
        # Prometheus metrics
        self._setup_prometheus_metrics()
        
        # Start metrics server
        start_http_server(port)
        logger.info(f"Prometheus metrics server started on port {port}")
    
    def _setup_prometheus_metrics(self):
        """Initialize all Prometheus metrics."""
        
        # Latency metrics
        self.end_to_end_latency = Histogram(
            'voice_agent_end_to_end_latency_ms',
            'End-to-end latency from speech to audio delivery',
            buckets=[50, 100, 200, 300, 400, 500, 600, 800, 1000, 1500, 2000, float('inf')]
        )
        
        self.stt_latency = Histogram(
            'voice_agent_stt_latency_ms',
            'Speech-to-text processing latency',
            buckets=[10, 20, 50, 100, 200, 500, 1000, float('inf')]
        )
        
        self.llm_latency = Histogram(
            'voice_agent_llm_latency_ms',
            'LLM processing latency',
            buckets=[50, 100, 200, 500, 1000, 2000, 5000, float('inf')]
        )
        
        self.tts_latency = Histogram(
            'voice_agent_tts_latency_ms',
            'Text-to-speech processing latency',
            buckets=[50, 100, 200, 500, 1000, 2000, float('inf')]
        )
        
        # Response time metrics
        self.response_time_95p = Summary(
            'voice_agent_response_time_95p_ms',
            '95th percentile response time'
        )
        
        self.response_time_avg = Summary(
            'voice_agent_response_time_avg_ms',
            'Average response time'
        )
        
        # Call metrics
        self.total_calls = Counter(
            'voice_agent_total_calls',
            'Total number of calls processed'
        )
        
        self.failed_call_setup = Counter(
            'voice_agent_failed_call_setup',
            'Number of failed call setups'
        )
        
        self.active_call_count = Gauge(
            'voice_agent_active_calls',
            'Number of currently active calls'
        )
        
        # Audio quality metrics
        self.mos_score = Histogram(
            'voice_agent_mos_score',
            'Mean Opinion Score for audio quality',
            buckets=[1.0, 2.0, 3.0, 4.0, 5.0]
        )
        
        self.jitter_ms = Histogram(
            'voice_agent_jitter_ms',
            'Audio jitter in milliseconds',
            buckets=[0, 5, 10, 20, 50, 100, 200, float('inf')]
        )
        
        self.packet_loss_rate = Histogram(
            'voice_agent_packet_loss_rate',
            'Packet loss rate as percentage',
            buckets=[0, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, float('inf')]
        )
        
        # System metrics
        self.cpu_usage = Gauge(
            'voice_agent_cpu_usage_percent',
            'CPU usage percentage'
        )
        
        self.memory_usage = Gauge(
            'voice_agent_memory_usage_mb',
            'Memory usage in MB'
        )
        
        # Latency targets
        self.latency_target_met = Counter(
            'voice_agent_latency_target_met',
            'Number of calls meeting <600ms latency target'
        )
        
        self.latency_target_missed = Counter(
            'voice_agent_latency_target_missed',
            'Number of calls missing <600ms latency target'
        )
    
    def start_call(self, call_id: str) -> LatencyMetrics:
        """Start tracking a new call."""
        metrics = LatencyMetrics()
        metrics.speech_start = time.time()
        self.active_calls[call_id] = metrics
        self.total_calls.inc()
        self.active_call_count.set(len(self.active_calls))
        logger.info(f"Started tracking call {call_id}")
        return metrics
    
    def mark_stt_start(self, call_id: str):
        """Mark the start of STT processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].stt_start = time.time()
    
    def mark_stt_end(self, call_id: str):
        """Mark the end of STT processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].stt_end = time.time()
    
    def mark_llm_start(self, call_id: str):
        """Mark the start of LLM processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].llm_start = time.time()
    
    def mark_llm_end(self, call_id: str):
        """Mark the end of LLM processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].llm_end = time.time()
    
    def mark_tts_start(self, call_id: str):
        """Mark the start of TTS processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].tts_start = time.time()
    
    def mark_tts_end(self, call_id: str):
        """Mark the end of TTS processing."""
        if call_id in self.active_calls:
            self.active_calls[call_id].tts_end = time.time()
    
    def mark_audio_delivered(self, call_id: str):
        """Mark when audio is delivered to the caller."""
        if call_id in self.active_calls:
            self.active_calls[call_id].audio_delivered = time.time()
    
    def end_call(self, call_id: str, mos_score: Optional[float] = None, 
                 jitter_ms: Optional[float] = None, packet_loss_rate: Optional[float] = None):
        """End call tracking and record final metrics."""
        if call_id not in self.active_calls:
            return
        
        metrics = self.active_calls.pop(call_id)
        self.active_call_count.set(len(self.active_calls))
        
        # Record latency metrics
        end_to_end_latency = metrics.get_end_to_end_latency()
        self.end_to_end_latency.observe(end_to_end_latency)
        
        stt_latency = metrics.get_stt_latency()
        self.stt_latency.observe(stt_latency)
        
        llm_latency = metrics.get_llm_latency()
        self.llm_latency.observe(llm_latency)
        
        tts_latency = metrics.get_tts_latency()
        self.tts_latency.observe(tts_latency)
        
        # Check latency target
        if end_to_end_latency < 600:
            self.latency_target_met.inc()
        else:
            self.latency_target_missed.inc()
        
        # Record audio quality metrics
        if mos_score is not None:
            self.mos_score.observe(mos_score)
        
        if jitter_ms is not None:
            self.jitter_ms.observe(jitter_ms)
        
        if packet_loss_rate is not None:
            self.packet_loss_rate.observe(packet_loss_rate)
        
        # Store in history for analysis
        self.call_history.append(metrics)
        
        # Keep only last 1000 calls in history
        if len(self.call_history) > 1000:
            self.call_history = self.call_history[-1000:]
        
        logger.info(f"Ended call {call_id} - E2E latency: {end_to_end_latency:.2f}ms")
    
    def record_failed_call_setup(self):
        """Record a failed call setup."""
        self.failed_call_setup.inc()
    
    def update_system_metrics(self):
        """Update system resource metrics."""
        self.cpu_usage.set(psutil.cpu_percent())
        self.memory_usage.set(psutil.virtual_memory().used / 1024 / 1024)  # MB
    
    def get_latency_stats(self) -> Dict[str, float]:
        """Get latency statistics from recent calls."""
        if not self.call_history:
            return {}
        
        recent_calls = self.call_history[-100:]  # Last 100 calls
        latencies = [call.get_end_to_end_latency() for call in recent_calls]
        
        latencies.sort()
        n = len(latencies)
        
        return {
            'avg_latency_ms': sum(latencies) / n,
            'p95_latency_ms': latencies[int(0.95 * n)] if n > 0 else 0,
            'p99_latency_ms': latencies[int(0.99 * n)] if n > 0 else 0,
            'min_latency_ms': min(latencies),
            'max_latency_ms': max(latencies),
            'target_met_percentage': sum(1 for l in latencies if l < 600) / n * 100
        }
    
    async def start_system_monitoring(self):
        """Start background system monitoring."""
        while True:
            try:
                self.update_system_metrics()
                await asyncio.sleep(5)  # Update every 5 seconds
            except Exception as e:
                logger.error(f"Error updating system metrics: {e}")
                await asyncio.sleep(5)

# Global metrics instance
metrics = VoiceAgentMetrics()
