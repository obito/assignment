
## 🚨 What Breaks at 1,000 Calls?

We have multiples points of failure: livekit server that is very hungry in resources. Handling 1k calls would end up in memory overflow and CPU exhaustion. 

A single SIP server can't handle 1k concurrent audio streams.

We would also maybe hit bandwidth limits, where around 64Mbps are needed for audio traffic.

On the external API side: we would hit absolutely every rate limits, we would need 2x the limits that are on AssemblyAI or Cartesia to handle 1k calls concurrently.

## 🔧 How to Fix It

### **1. Horizontal Scaling Architecture**

- LiveKit Cluster: 3 nodes x 8 CPU cores, 32GB RAM
- SIP Server Pool: 5 nodes × 4 CPU cores, 16GB RAM
- We would have auto-scaling workers based on CPU/memory usage
- In the front, a HAProxy load balancer

### **2. Self-Hosted AI Services**

We could run almost every service except maybe the LLM part on our own hardware: Whisper for the SST, Coqui for the TSS part. If you want to really optimize everything, we can try to self-host Llama 3, however it needs way more effort to do so, and it directly impacts the quality of the response from agents. 

We need to see if the price is really worth it.


## ⏱️ Current Latency Bottlenecks`

Biggest current bottleneck here is clearly the LLM, with a 99th percentile at 3.49seconds, and a 75th percentile at around 1.5seconds. 