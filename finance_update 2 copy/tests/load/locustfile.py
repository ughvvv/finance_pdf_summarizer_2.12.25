"""Load testing scenarios using locust."""

import json
import random
from typing import Dict, Any
from pathlib import Path
from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner

from tests.helpers import create_test_report

class ReportProcessingUser(HttpUser):
    """Simulates user processing reports."""
    
    wait_time = between(1, 5)  # Wait 1-5 seconds between tasks
    
    def on_start(self):
        """Setup before starting tasks."""
        self.test_reports = self._generate_test_reports()
        self.metrics = {
            'processing_times': [],
            'success_rate': {'success': 0, 'failure': 0},
            'error_types': {}
        }
    
    def _generate_test_reports(self, num_reports: int = 10) -> list:
        """Generate test report data."""
        reports = []
        for i in range(num_reports):
            report = create_test_report(f"load_test_report_{i}.pdf")
            # Vary report sizes
            report['text'] = report['text'] * random.randint(1, 5)
            reports.append(report)
        return reports
    
    @task(3)  # Higher weight for common operation
    def process_single_report(self):
        """Process a single report."""
        report = random.choice(self.test_reports)
        with self.client.post(
            "/api/process",
            json={"report": report},
            catch_response=True
        ) as response:
            try:
                if response.status_code == 200:
                    self.metrics['success_rate']['success'] += 1
                    self.metrics['processing_times'].append(
                        response.elapsed.total_seconds()
                    )
                else:
                    self.metrics['success_rate']['failure'] += 1
                    error_type = response.json().get('error_type', 'unknown')
                    self.metrics['error_types'][error_type] = \
                        self.metrics['error_types'].get(error_type, 0) + 1
                    response.failure(f"Error: {response.text}")
            except Exception as e:
                self.metrics['success_rate']['failure'] += 1
                self.metrics['error_types']['exception'] = \
                    self.metrics['error_types'].get('exception', 0) + 1
                response.failure(f"Exception: {str(e)}")
    
    @task
    def process_batch_reports(self):
        """Process multiple reports in batch."""
        batch_size = random.randint(2, 5)
        reports = random.sample(self.test_reports, batch_size)
        
        with self.client.post(
            "/api/process/batch",
            json={"reports": reports},
            catch_response=True
        ) as response:
            try:
                if response.status_code == 200:
                    self.metrics['success_rate']['success'] += batch_size
                    self.metrics['processing_times'].append(
                        response.elapsed.total_seconds() / batch_size
                    )
                else:
                    self.metrics['success_rate']['failure'] += batch_size
                    error_type = response.json().get('error_type', 'unknown')
                    self.metrics['error_types'][error_type] = \
                        self.metrics['error_types'].get(error_type, 0) + 1
                    response.failure(f"Batch Error: {response.text}")
            except Exception as e:
                self.metrics['success_rate']['failure'] += batch_size
                self.metrics['error_types']['exception'] = \
                    self.metrics['error_types'].get('exception', 0) + 1
                response.failure(f"Batch Exception: {str(e)}")

class LongRunningUser(HttpUser):
    """Simulates users with long-running operations."""
    
    wait_time = between(10, 30)  # Longer wait times
    
    def on_start(self):
        """Setup before starting tasks."""
        self.large_reports = self._generate_large_reports()
        self.metrics = {
            'processing_times': [],
            'timeouts': 0,
            'success_rate': {'success': 0, 'failure': 0}
        }
    
    def _generate_large_reports(self, num_reports: int = 3) -> list:
        """Generate large test reports."""
        reports = []
        for i in range(num_reports):
            report = create_test_report(f"large_report_{i}.pdf")
            # Create very large reports
            report['text'] = report['text'] * random.randint(10, 20)
            reports.append(report)
        return reports
    
    @task
    def process_large_report(self):
        """Process a large report."""
        report = random.choice(self.large_reports)
        with self.client.post(
            "/api/process",
            json={"report": report},
            catch_response=True,
            timeout=300  # 5 minute timeout
        ) as response:
            try:
                if response.status_code == 200:
                    self.metrics['success_rate']['success'] += 1
                    self.metrics['processing_times'].append(
                        response.elapsed.total_seconds()
                    )
                else:
                    self.metrics['success_rate']['failure'] += 1
                    response.failure(f"Error: {response.text}")
            except Exception as e:
                self.metrics['success_rate']['failure'] += 1
                if "timeout" in str(e).lower():
                    self.metrics['timeouts'] += 1
                response.failure(f"Exception: {str(e)}")

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Initialize test metrics."""
    if isinstance(environment.runner, MasterRunner):
        print("Starting load test...")
        environment.runner.stats.clear_all()

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Generate test report."""
    if isinstance(environment.runner, MasterRunner):
        stats = environment.runner.stats
        
        # Calculate metrics
        total_requests = stats.total.num_requests
        total_failures = stats.total.num_failures
        avg_response_time = stats.total.avg_response_time
        
        # Generate report
        report = {
            'summary': {
                'total_requests': total_requests,
                'total_failures': total_failures,
                'success_rate': (
                    (total_requests - total_failures) / total_requests * 100
                    if total_requests > 0 else 0
                ),
                'average_response_time': avg_response_time,
                'requests_per_second': stats.total.current_rps
            },
            'response_times': {
                'median': stats.total.get_response_time_percentile(0.5),
                'p95': stats.total.get_response_time_percentile(0.95),
                'p99': stats.total.get_response_time_percentile(0.99)
            },
            'errors': [
                {
                    'name': error,
                    'occurrences': count
                }
                for error, count in stats.errors.items()
            ]
        }
        
        # Save report
        report_path = Path('load_test_results.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print("\n=== Load Test Results ===")
        print(f"Total Requests: {total_requests}")
        print(f"Success Rate: {report['summary']['success_rate']:.2f}%")
        print(f"Avg Response Time: {avg_response_time:.2f}ms")
        print(f"Requests/Second: {stats.total.current_rps:.2f}")
        print(f"\nDetailed report saved to: {report_path}")
