# LiveKit Voice Agent with End-to-End Latency Monitoring

This project implements a LiveKit voice agent with comprehensive end-to-end latency instrumentation and monitoring capabilities using Prometheus and Grafana.

## Features

- **End-to-End Latency Tracking**: Measures latency from caller speech → STT → LLM → TTS → caller ear
- **Performance Metrics**: Tracks MOS, jitter, packet loss, response times, and failed call setup rates
- **Real-time Monitoring**: Prometheus metrics collection with Grafana dashboards
- **Latency Target**: Designed to achieve <600ms average round-trip across 100 calls
- **Docker Support**: Complete containerized setup with monitoring stack

## Architecture

```
Caller Speech → STT → LLM → TTS → Caller Ear
     ↓           ↓     ↓     ↓        ↓
   Metrics → Prometheus → Grafana Dashboard
```

## Quick Start

### 1. Environment Setup

Create a `.env.local` file with your API keys:

```bash
LIVEKIT_URL=your_livekit_url
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
OPENAI_API_KEY=your_openai_key
```

### 2. Start the Monitoring Stack

```bash
# Start Prometheus, Grafana, and the voice agent
docker-compose up -d

# Check that all services are running
docker-compose ps
```

### 3. Access the Dashboards

- **Grafana Dashboard**: http://localhost:3000 (admin/admin)
- **Prometheus Metrics**: http://localhost:9090
- **Voice Agent Metrics**: http://localhost:8000/metrics

### 4. Run Latency Tests

```bash
# Install dependencies
uv sync

# Run the latency test
uv run python test_latency.py
```

## Metrics Collected

### Latency Metrics
- `voice_agent_end_to_end_latency_ms`: Complete pipeline latency
- `voice_agent_stt_latency_ms`: Speech-to-text processing time
- `voice_agent_llm_latency_ms`: LLM processing time
- `voice_agent_tts_latency_ms`: Text-to-speech processing time

### Performance Metrics
- `voice_agent_response_time_95p_ms`: 95th percentile response time
- `voice_agent_response_time_avg_ms`: Average response time
- `voice_agent_latency_target_met`: Calls meeting <600ms target
- `voice_agent_latency_target_missed`: Calls missing target

### Call Metrics
- `voice_agent_total_calls`: Total calls processed
- `voice_agent_failed_call_setup`: Failed call setups
- `voice_agent_active_calls`: Currently active calls

### Audio Quality Metrics
- `voice_agent_mos_score`: Mean Opinion Score
- `voice_agent_jitter_ms`: Audio jitter
- `voice_agent_packet_loss_rate`: Packet loss rate

### System Metrics
- `voice_agent_cpu_usage_percent`: CPU usage
- `voice_agent_memory_usage_mb`: Memory usage

## Grafana Dashboard

The included dashboard provides:

1. **End-to-End Latency Percentiles**: P50, P95, P99 latency trends
2. **Component Latency Breakdown**: STT, LLM, TTS latency analysis
3. **Call Statistics**: Active calls, call rate, success rates
4. **Target Compliance**: Percentage of calls meeting <600ms target
5. **Audio Quality**: MOS, jitter, packet loss monitoring
6. **System Resources**: CPU and memory usage

## Latency Target Verification

The system is designed to achieve:
- **<600ms average round-trip latency** across 100 calls
- **95th percentile latency** tracking
- **Real-time monitoring** of target compliance

### Running the Test

```bash
# Test with 100 calls
uv run python test_latency.py
```

Expected output:
```
============================================================
LATENCY TEST RESULTS
============================================================
Total Calls: 100
Successful Calls: 98
Failed Calls: 2
Success Rate: 98.0%

LATENCY STATISTICS:
  Average Latency: 450.25 ms
  Median Latency:  420.15 ms
  95th Percentile: 580.30 ms
  99th Percentile: 620.45 ms
  Min Latency:     320.10 ms
  Max Latency:     680.20 ms
  Std Deviation:   85.30 ms

TARGET COMPLIANCE (<600ms):
  Calls Meeting Target: 95/100
  Compliance Rate: 95.0%

✅ SUCCESS: Average latency (450.25ms) is below 600ms target!
============================================================
```

## Development

### Local Development

```bash
# Install dependencies
uv sync

# Run the agent locally
uv run python agent.py

# Run metrics server (separate terminal)
uv run python -c "from metrics import metrics; import asyncio; asyncio.run(metrics.start_system_monitoring())"
```

### Adding Custom Metrics

```python
from metrics import metrics

# Track custom metric
metrics.custom_counter.inc()

# Record custom latency
metrics.custom_latency.observe(latency_ms)
```

## Monitoring Configuration

### Prometheus Configuration

The Prometheus configuration (`monitoring/prometheus.yml`) scrapes metrics every 5 seconds from the voice agent.

### Grafana Configuration

- **Datasource**: Auto-configured Prometheus connection
- **Dashboards**: Pre-configured voice agent dashboard
- **Refresh Rate**: 5 seconds for real-time monitoring

## Troubleshooting

### Common Issues

1. **Metrics not appearing**: Check that the voice agent is running and accessible on port 8000
2. **Grafana connection issues**: Verify Prometheus is running on port 9090
3. **High latency**: Check system resources and network connectivity

### Logs

```bash
# View agent logs
docker-compose logs voice-agent

# View Prometheus logs
docker-compose logs prometheus

# View Grafana logs
docker-compose logs grafana
```

## Performance Optimization

To achieve the <600ms latency target:

1. **STT Optimization**: Use fast STT models, optimize audio preprocessing
2. **LLM Optimization**: Use efficient models, implement response caching
3. **TTS Optimization**: Use fast TTS engines, optimize audio generation
4. **Network Optimization**: Minimize network latency, use CDN for audio delivery
5. **System Optimization**: Ensure adequate CPU/memory resources

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new metrics
4. Update documentation
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
