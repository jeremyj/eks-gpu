# EKS CloudWatch Monitor

Analyze EKS cluster resource utilization via CloudWatch Container Insights.

## Installation

```bash
pip install -e .
```

## Usage

```bash
# Full cluster analysis (7 days)
eks-monitor analyze --cluster-name prod

# Last 24 hours, specific namespace
eks-monitor analyze --cluster-name prod --hours 24 --namespace default

# Exclude GPU nodes
eks-monitor analyze --cluster-name prod --exclude-gpu

# Using specific AWS profile
eks-monitor analyze --cluster-name prod --profile my-profile --region us-east-1
```

### Options

```
Required:
  --cluster-name        EKS cluster name

Time Range:
  --hours               Hours of data (default: 168 = 7 days)
  --period              Aggregation period in seconds (default: 3600 = 1 hour)

Filters:
  --namespace           Filter to specific namespace(s), repeatable
  --exclude-gpu         Exclude GPU nodegroups
  --nodegroup           Filter to specific nodegroup

AWS:
  --profile             AWS profile name
  --region              AWS region (default: eu-west-1)

Output:
  --output-dir          Directory for JSON output (default: ./reports)
  --quiet               Suppress progress output
```

## IAM Requirements

See `iam-policy.json` for required permissions:
- CloudWatch: `GetMetricStatistics`, `ListMetrics`, `GetMetricData`
- EKS: `DescribeCluster`, `ListNodegroups`, `DescribeNodegroup`

## Output

JSON report with:
- Cluster summary (CPU, memory, network averages/maximums)
- Per-node metrics
- Per-workload metrics (aggregated by deployment/statefulset)
- Per-pod metrics

## Cron Example

```bash
# Run daily at 6am, collecting previous 24h at 1-minute resolution
# Note: % must be escaped as \% in crontab
0 6 * * * /usr/local/bin/eks-monitor analyze --cluster-name prod --hours 24 --end-time $(date -u +\%Y-\%m-\%dT00:00:00) --period 60 --output-dir /var/reports --quiet
```
