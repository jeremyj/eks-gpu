# EKS GPU Tools - AI Instructions

## Project Structure

- `eks_nvidia_tools/` - Main CLI for EKS AMI and NVIDIA driver management
- `eks-cloudwatch-monitor/` - Separate tool for EKS cluster resource analysis via CloudWatch
- `docs/` - User-facing documentation
- `reports/` - Generated analysis reports (gitignored)

## eks-cloudwatch-monitor

- Installed via `pip install -e .` in `eks-cloudwatch-monitor/`
- Entry point: `eks-monitor` CLI
- Cron job runs daily at 6 AM collecting 24h of 1-minute resolution metrics
- **Crontab gotcha**: `%` must be escaped as `\%` in crontab entries (cron interprets `%` as newline)

## Versioning

- Tags follow semver: `vMAJOR.MINOR.PATCH`
- Current: v1.6.0
