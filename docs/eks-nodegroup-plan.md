# EKS Nodegroup Planning for prod Cluster

## Current State

**Cluster:** prod (EKS 1.32, eu-west-1)

| Nodegroup | Instance | Nodes | vCPU | Memory | Capacity |
|-----------|----------|-------|------|--------|----------|
| nodegroup-1a-arm | c7gn.2xlarge | 3 (fixed) | 8 | 16GB | On-Demand |
| nodegroup-1b-arm | c7gn.2xlarge | 3 (fixed) | On-Demand |
| **Total** | | **6** | **48** | **96GB** | |

**Current utilization:** ~36GB memory (~40%), <5 vCPU (~10%)

### CloudWatch Memory Analysis (Jan 20-27, 2026)

**Cluster-level stats (excluding GPU nodes):**
- **Average node memory:** 40-50%
- **Maximum node memory:** Peaks at **78-79%** (triggering 80% alarm)
- High spikes correlated with uneven pod distribution

**Root cause of memory alarms:**
- Celery pods are the largest memory consumers (~5GB each)
- When 2+ celery pods land on the same node (16GB), that node reaches 62%+ utilization
- Combined with system pods + other workloads → exceeds 80% threshold
- No pod anti-affinity rules to prevent co-location of memory-heavy pods

## Workloads (excluding GPU-managed)

| Workload | Pods | Memory/pod | Total | Spot OK? |
|----------|------|------------|-------|----------|
| celery | 4 | ~5GB | ~20GB | Yes |
| backend | 4 | ~1.8GB | ~7.2GB | Yes |
| celery-encoding | 4 | ~900Mi | ~3.5GB | Yes |
| frontend | 4 | ~450Mi | ~1.8GB | Yes |
| rabbitmq | 3 | ~250Mi | ~750Mi | Yes (clustered) |
| redis-master | 1 | ~60Mi | ~60Mi | Yes |
| flower | 1 | ~750Mi | ~750Mi | Yes |
| Others | ~10 | <200Mi | ~2GB | Yes |

**All workloads can run on Spot** - nothing is truly stateful (rabbitmq is clustered).

---

## Proposed Nodegroup Strategy

### Design Principles
1. **Hybrid RI + Spot** - Reserved for baseline, Spot for burst
2. **Enable autoscaling** - Scale based on actual demand
3. **Maintain Multi-AZ** - Keep pods distributed across 1a/1b
4. **Separate by resource profile** - Memory-heavy vs network-heavy

### Proposed Nodegroups

**Baseline Capacity (3yr Reserved, No Upfront):**

| Nodegroup | Instance | Count | Capacity | AZ | Purpose |
|-----------|----------|-------|----------|-----|---------|
| workers-ri-1a | c7gn.2xlarge | 1 | **3yr RI** | eu-west-1a | celery, backend (baseline) |
| workers-ri-1b | c7gn.2xlarge | 1 | **3yr RI** | eu-west-1b | celery, backend (baseline) |
| network-ri-1a | c7gn.xlarge | 1 | **3yr RI** | eu-west-1a | frontend, tusd, rabbitmq, redis |
| network-ri-1b | c7gn.xlarge | 1 | **3yr RI** | eu-west-1b | frontend, tusd, rabbitmq, redis |

**Burst Capacity (Spot):**

| Nodegroup | Instance | Min | Max | Capacity | AZ | Purpose |
|-----------|----------|-----|-----|----------|-----|---------|
| workers-spot-1a | c7gn.2xlarge | 0 | 3 | **Spot** | eu-west-1a | celery scaling |
| workers-spot-1b | c7gn.2xlarge | 0 | 3 | **Spot** | eu-west-1b | celery scaling |
| network-spot-1a | c7gn.xlarge | 0 | 2 | **Spot** | eu-west-1a | frontend scaling |
| network-spot-1b | c7gn.xlarge | 0 | 2 | **Spot** | eu-west-1b | frontend scaling |

**Total: 8 nodegroups** (4 RI baseline + 4 Spot burst)

**Note:**
- Baseline RI nodes handle normal load (always running)
- Spot burst nodes scale up during peaks, scale to 0 when idle
- If Spot unavailable, baseline still serves traffic

### Instance Specs

| Instance | vCPU | Memory | Network | Use Case |
|----------|------|--------|---------|----------|
| c7gn.xlarge | 4 | 8GB | Up to 40 Gbps | Network-heavy (frontend/tusd), light pods |
| c7gn.2xlarge | 8 | 16GB | Up to 50 Gbps | Memory-heavy + network-heavy (celery, backend) |

### Scheduling Strategy

**Node Labels:**
```yaml
# All worker nodegroups (RI and Spot)
workload-type: workers

# All network nodegroups (RI and Spot)
workload-type: network

# Capacity type labels (added automatically by EKS)
eks.amazonaws.com/capacityType: ON_DEMAND  # for RI nodes
eks.amazonaws.com/capacityType: SPOT       # for Spot nodes
```

**Spot Taints (Spot nodegroups only):**
```yaml
- key: "eks.amazonaws.com/capacityType"
  value: "SPOT"
  effect: "PreferNoSchedule"
```
This makes scheduler prefer RI nodes, but allows Spot when RI is full.

**Pod Configuration:**

*Baseline-only pods (NO Spot toleration - RI nodes only):*
- redis-master: `nodeSelector: {workload-type: network}` (no Spot toleration)
- tus-hook-listener: `nodeSelector: {workload-type: network}` (no Spot toleration)

*Burst-capable pods (with Spot toleration):*
- Celery/celery-encoding/backend/flower: `nodeSelector: {workload-type: workers}` + Spot toleration
- Frontend/tusd/rabbitmq: `nodeSelector: {workload-type: network}` + Spot toleration
- Light pods: `nodeSelector: {workload-type: network}` + Spot toleration

**redis-master and tus-hook-listener always run on RI baseline nodes.**

**Pod Anti-Affinity (Critical for preventing memory alarms):**
```yaml
# Add to celery deployment to prevent co-location
affinity:
  podAntiAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
    - labelSelector:
        matchLabels:
          app: celery
      topologyKey: kubernetes.io/hostname
```
This ensures celery pods are distributed across different nodes, preventing 2 celery pods (10GB) from landing on the same 16GB node.

---

## Resource Requests to Define

Based on observed usage, set these requests/limits:

| Workload | CPU Request | CPU Limit | Memory Request | Memory Limit |
|----------|-------------|-----------|----------------|--------------|
| celery | 50m | 500m | 5Gi | 6Gi |
| backend | 25m | 200m | 1.8Gi | 2Gi |
| celery-encoding | 10m | 100m | 900Mi | 1Gi |
| frontend | 10m | 200m | 500Mi | 600Mi |
| rabbitmq | 100m | 200m | 300Mi | 500Mi |
| redis-master | 20m | 100m | 100Mi | 200Mi |
| flower | 10m | 100m | 800Mi | 1Gi |
| tusd | 10m | 300m | 50Mi | 100Mi |

---

## Cost Comparison (Estimates)

**Current (On-Demand only):**
- 6 × c7gn.2xlarge On-Demand = ~$0.55 × 6 = $3.30/hr = **~$2,409/month**

**Proposed (Hybrid RI + Spot):**

*Baseline (3yr RI No Upfront, always running):*
- 2 × c7gn.2xlarge RI = ~$0.36 × 2 = $0.72/hr
- 2 × c7gn.xlarge RI = ~$0.18 × 2 = $0.36/hr
- **Baseline:** $1.08/hr = **~$788/month**

*Burst (Spot, only when scaling):*
- Additional c7gn.2xlarge Spot = ~$0.20/hr each
- Additional c7gn.xlarge Spot = ~$0.10/hr each

| Scenario | Monthly Cost | vs Current |
|----------|--------------|------------|
| Baseline only (4 RI nodes) | **~$788/month** | **67% savings** |
| Baseline + 2 Spot burst | ~$934/month | 61% savings |
| Full burst (RI + all Spot) | ~$1,226/month | 49% savings |

**Key benefits:**
- Guaranteed capacity with RI baseline
- Flexibility to scale with Spot
- No 2-minute interruption risk for critical baseline workloads
- ~67% savings at baseline vs current On-Demand

---

## Implementation Steps

1. **Purchase Reserved Instances** (3yr No Upfront)
   - 2 × c7gn.2xlarge (eu-west-1a, eu-west-1b)
   - 2 × c7gn.xlarge (eu-west-1a, eu-west-1b)
2. **Create RI nodegroups** (fixed size = 1 each, On-Demand capacity)
3. **Create Spot nodegroups** (min=0, autoscaling enabled)
4. **Update pod specs** with:
   - nodeSelectors for workload routing
   - Spot tolerations
   - **podAntiAffinity for celery** (prevents memory alarms)
5. **Define resource requests/limits** for all workloads
6. **Create PodDisruptionBudgets** for all workloads
7. **Migrate workloads** by cordoning old nodes
8. **Delete old nodegroups** after successful migration
9. **Configure cluster autoscaler** for Spot nodegroups

### PodDisruptionBudgets (Critical for Spot reliability)

```yaml
# Celery workers
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: celery-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: celery
---
# RabbitMQ cluster
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: rabbitmq-pdb
spec:
  minAvailable: 2  # Keep quorum during interruptions
  selector:
    matchLabels:
      app: rabbitmq
---
# Backend
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: backend-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: backend
```

---

## Verification

1. Check pod distribution: `kubectl get pods -o wide`
2. Verify node labels: `kubectl get nodes --show-labels`
3. Test Spot interruption handling with PodDisruptionBudgets
4. Monitor costs in AWS Cost Explorer after 1 week
5. Verify autoscaling by checking ASG activity
