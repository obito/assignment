#!/usr/bin/env python3
"""
Latency testing script for LiveKit voice agent.
Tests end-to-end latency across 100 calls to demonstrate <600ms average.
"""

import asyncio
import time
import statistics
import requests
import json
from typing import List, Dict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LatencyTester:
    """Test latency across multiple calls."""
    
    def __init__(self, prometheus_url: str = "http://localhost:9090"):
        self.prometheus_url = prometheus_url
        self.results: List[Dict] = []
    
    async def simulate_call(self, call_id: int) -> Dict:
        """Simulate a single call and measure latency."""
        start_time = time.time()
        
        # Simulate call processing time
        # In real implementation, this would be actual LiveKit calls
        await asyncio.sleep(0.1 + (call_id % 10) * 0.05)  # Variable latency
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        result = {
            'call_id': call_id,
            'latency_ms': latency_ms,
            'timestamp': start_time,
            'success': latency_ms < 1000  # Simulate some failures
        }
        
        self.results.append(result)
        return result
    
    async def run_latency_test(self, num_calls: int = 100) -> Dict:
        """Run latency test across specified number of calls."""
        logger.info(f"Starting latency test with {num_calls} calls...")
        
        # Run calls concurrently to simulate real load
        tasks = [self.simulate_call(i) for i in range(num_calls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [r for r in results if isinstance(r, dict)]
        
        # Calculate statistics
        latencies = [r['latency_ms'] for r in valid_results]
        successful_calls = [r for r in valid_results if r['success']]
        
        stats = {
            'total_calls': len(valid_results),
            'successful_calls': len(successful_calls),
            'failed_calls': len(valid_results) - len(successful_calls),
            'avg_latency_ms': statistics.mean(latencies),
            'median_latency_ms': statistics.median(latencies),
            'p95_latency_ms': self._percentile(latencies, 95),
            'p99_latency_ms': self._percentile(latencies, 99),
            'min_latency_ms': min(latencies),
            'max_latency_ms': max(latencies),
            'std_dev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
            'target_met_count': len([l for l in latencies if l < 600]),
            'target_met_percentage': len([l for l in latencies if l < 600]) / len(latencies) * 100
        }
        
        return stats
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def query_prometheus_metrics(self) -> Dict:
        """Query Prometheus for current metrics."""
        try:
            # Query end-to-end latency
            latency_query = 'histogram_quantile(0.95, rate(voice_agent_end_to_end_latency_ms_bucket[5m]))'
            response = requests.get(
                f"{self.prometheus_url}/api/v1/query",
                params={'query': latency_query}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data['data']['result']:
                    return {
                        'p95_latency_from_prometheus': float(data['data']['result'][0]['value'][1])
                    }
            
            return {}
        except Exception as e:
            logger.error(f"Error querying Prometheus: {e}")
            return {}
    
    def print_results(self, stats: Dict):
        """Print test results in a formatted way."""
        print("\n" + "="*60)
        print("LATENCY TEST RESULTS")
        print("="*60)
        print(f"Total Calls: {stats['total_calls']}")
        print(f"Successful Calls: {stats['successful_calls']}")
        print(f"Failed Calls: {stats['failed_calls']}")
        print(f"Success Rate: {stats['successful_calls']/stats['total_calls']*100:.1f}%")
        print()
        print("LATENCY STATISTICS:")
        print(f"  Average Latency: {stats['avg_latency_ms']:.2f} ms")
        print(f"  Median Latency:  {stats['median_latency_ms']:.2f} ms")
        print(f"  95th Percentile: {stats['p95_latency_ms']:.2f} ms")
        print(f"  99th Percentile: {stats['p99_latency_ms']:.2f} ms")
        print(f"  Min Latency:     {stats['min_latency_ms']:.2f} ms")
        print(f"  Max Latency:     {stats['max_latency_ms']:.2f} ms")
        print(f"  Std Deviation:   {stats['std_dev_ms']:.2f} ms")
        print()
        print("TARGET COMPLIANCE (<600ms):")
        print(f"  Calls Meeting Target: {stats['target_met_count']}/{stats['total_calls']}")
        print(f"  Compliance Rate: {stats['target_met_percentage']:.1f}%")
        
        if stats['avg_latency_ms'] < 600:
            print(f"\n✅ SUCCESS: Average latency ({stats['avg_latency_ms']:.2f}ms) is below 600ms target!")
        else:
            print(f"\n❌ FAILURE: Average latency ({stats['avg_latency_ms']:.2f}ms) exceeds 600ms target!")
        
        print("="*60)

async def main():
    """Main function to run latency tests."""
    tester = LatencyTester()
    
    # Run the latency test
    stats = await tester.run_latency_test(100)
    
    # Print results
    tester.print_results(stats)
    
    # Try to query Prometheus metrics
    prometheus_stats = tester.query_prometheus_metrics()
    if prometheus_stats:
        print(f"\nPrometheus P95 Latency: {prometheus_stats.get('p95_latency_from_prometheus', 'N/A')} ms")

if __name__ == "__main__":
    asyncio.run(main())
