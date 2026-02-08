# Manual Guide: Create 3 EKS Nodegroups in 3 AZs with AL2023 ARM

## Prerequisites

- AWS CLI configured with `mnemonica` profile
- Region: `eu-west-1`

## Reference Values

| Parameter | Value |
|-----------|-------|
| AWS Profile | `mnemonica` |
| Cluster | `prod` |
| VPC | `vpc-024077f93b8e67581` |
| K8s Version | `1.32` |
| AMI Type | `AL2023_ARM_64_STANDARD` |
| Release Version | `1.32.9-20260120` |
| Instance Type | `c7gn.2xlarge` |
| Disk Size | `200` GB |
| Scaling | min=3, max=3, desired=3 |
| Node Role | `arn:aws:iam::828879644785:role/AmazonEKSNodeRole-prod` |
| SSH Key | `eks-prod-01` |
| Source Security Group | `sg-0459de7704ebc9276` |
| Public Route Table | `rtb-076e9413f16df7afc` |
| VPC Peering Connection | `pcx-02d9a90bf179ca438` |
| S3 VPC Endpoint | `vpce-0e7d1f9e40e09a100` |
| S3 Prefix List | `pl-6da54004` |

## Existing Private Subnets

| AZ | Subnet ID |
|----|-----------|
| eu-west-1a | `subnet-0c733fcd8ec63a3f3` |
| eu-west-1b | `subnet-0524749aaaec69b3c` |

---

# PHASE 1: Create eu-west-1c Infrastructure

## Step 1: Create Public Subnet in eu-west-1c

```bash
aws ec2 create-subnet --profile mnemonica \
  --vpc-id vpc-024077f93b8e67581 \
  --cidr-block 172.50.32.0/20 \
  --availability-zone eu-west-1c \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=EKS-PROD-subnet-public3-eu-west-1c}]'
```

**Save the output `SubnetId` as `PUBLIC_SUBNET_1C`**

---

## Step 2: Associate Public Subnet with Public Route Table

```bash
aws ec2 associate-route-table --profile mnemonica \
  --subnet-id <PUBLIC_SUBNET_1C> \
  --route-table-id rtb-076e9413f16df7afc
```

---

## Step 3: Allocate Elastic IP for NAT Gateway

```bash
aws ec2 allocate-address --profile mnemonica \
  --domain vpc \
  --tag-specifications 'ResourceType=elastic-ip,Tags=[{Key=Name,Value=EKS-PROD-eip-eu-west-1c}]'
```

**Save the output `AllocationId` as `EIP_ALLOCATION_ID`**

---

## Step 4: Create NAT Gateway in Public Subnet

```bash
aws ec2 create-nat-gateway --profile mnemonica \
  --subnet-id <PUBLIC_SUBNET_1C> \
  --allocation-id <EIP_ALLOCATION_ID> \
  --tag-specifications 'ResourceType=natgateway,Tags=[{Key=Name,Value=EKS-PROD-nat-public3-eu-west-1c}]'
```

**Save the output `NatGatewayId` as `NAT_GATEWAY_1C`**

---

## Step 5: Wait for NAT Gateway to Become Available

```bash
aws ec2 wait nat-gateway-available --profile mnemonica --nat-gateway-ids <NAT_GATEWAY_1C>
```

---

## Step 6: Create Private Subnet in eu-west-1c

```bash
aws ec2 create-subnet --profile mnemonica \
  --vpc-id vpc-024077f93b8e67581 \
  --cidr-block 172.50.160.0/20 \
  --availability-zone eu-west-1c \
  --tag-specifications 'ResourceType=subnet,Tags=[{Key=Name,Value=EKS-PROD-subnet-private3-eu-west-1c}]'
```

**Save the output `SubnetId` as `PRIVATE_SUBNET_1C`**

---

## Step 7: Create Private Route Table

```bash
aws ec2 create-route-table --profile mnemonica \
  --vpc-id vpc-024077f93b8e67581 \
  --tag-specifications 'ResourceType=route-table,Tags=[{Key=Name,Value=EKS-PROD-rtb-private3-eu-west-1c}]'
```

**Save the output `RouteTableId` as `RTB_PRIVATE_1C`**

---

## Step 8: Add Routes to Private Route Table

### 8a: Default route via NAT Gateway

```bash
aws ec2 create-route --profile mnemonica \
  --route-table-id <RTB_PRIVATE_1C> \
  --destination-cidr-block 0.0.0.0/0 \
  --nat-gateway-id <NAT_GATEWAY_1C>
```

### 8b: VPC Peering route (10.0.0.0/20)

```bash
aws ec2 create-route --profile mnemonica \
  --route-table-id <RTB_PRIVATE_1C> \
  --destination-cidr-block 10.0.0.0/20 \
  --vpc-peering-connection-id pcx-02d9a90bf179ca438
```

### 8c: VPC Peering route (10.0.16.0/20)

```bash
aws ec2 create-route --profile mnemonica \
  --route-table-id <RTB_PRIVATE_1C> \
  --destination-cidr-block 10.0.16.0/20 \
  --vpc-peering-connection-id pcx-02d9a90bf179ca438
```

### 8d: Associate Route Table with S3 VPC Endpoint

```bash
aws ec2 modify-vpc-endpoint --profile mnemonica \
  --vpc-endpoint-id vpce-0e7d1f9e40e09a100 \
  --add-route-table-ids <RTB_PRIVATE_1C>
```

---

## Step 9: Associate Private Subnet with Route Table

```bash
aws ec2 associate-route-table --profile mnemonica \
  --subnet-id <PRIVATE_SUBNET_1C> \
  --route-table-id <RTB_PRIVATE_1C>
```

---

# PHASE 2: Create EKS Nodegroups

## Subnet Summary

| AZ | Private Subnet ID |
|----|-------------------|
| eu-west-1a | `subnet-0c733fcd8ec63a3f3` |
| eu-west-1b | `subnet-0524749aaaec69b3c` |
| eu-west-1c | `<PRIVATE_SUBNET_1C>` (from Step 6) |

---

## Step 10: Create Nodegroup in eu-west-1a

```bash
aws eks create-nodegroup --profile mnemonica \
  --cluster-name prod \
  --nodegroup-name nodegroup-1a-arm-al2023 \
  --scaling-config minSize=3,maxSize=3,desiredSize=3 \
  --disk-size 200 \
  --subnets subnet-0c733fcd8ec63a3f3 \
  --instance-types c7gn.2xlarge \
  --ami-type AL2023_ARM_64_STANDARD \
  --capacity-type ON_DEMAND \
  --node-role arn:aws:iam::828879644785:role/AmazonEKSNodeRole-prod \
  --remote-access ec2SshKey=eks-prod-01,sourceSecurityGroups=sg-0459de7704ebc9276 \
  --update-config maxUnavailable=1 \
  --labels nodegroup-generation=v2 \
  --tags k8s.io/cluster-autoscaler/enabled=true,k8s.io/cluster-autoscaler/prod=present \
  --release-version 1.32.9-20260120
```

---

## Step 11: Create Nodegroup in eu-west-1b

```bash
aws eks create-nodegroup --profile mnemonica \
  --cluster-name prod \
  --nodegroup-name nodegroup-1b-arm-al2023 \
  --scaling-config minSize=3,maxSize=3,desiredSize=3 \
  --disk-size 200 \
  --subnets subnet-0524749aaaec69b3c \
  --instance-types c7gn.2xlarge \
  --ami-type AL2023_ARM_64_STANDARD \
  --capacity-type ON_DEMAND \
  --node-role arn:aws:iam::828879644785:role/AmazonEKSNodeRole-prod \
  --remote-access ec2SshKey=eks-prod-01,sourceSecurityGroups=sg-0459de7704ebc9276 \
  --update-config maxUnavailable=1 \
  --labels nodegroup-generation=v2 \
  --tags k8s.io/cluster-autoscaler/enabled=true,k8s.io/cluster-autoscaler/prod=present \
  --release-version 1.32.9-20260120
```

---

## Step 12: Create Nodegroup in eu-west-1c

```bash
aws eks create-nodegroup --profile mnemonica \
  --cluster-name prod \
  --nodegroup-name nodegroup-1c-arm-al2023 \
  --scaling-config minSize=3,maxSize=3,desiredSize=3 \
  --disk-size 200 \
  --subnets <PRIVATE_SUBNET_1C> \
  --instance-types c7gn.2xlarge \
  --ami-type AL2023_ARM_64_STANDARD \
  --capacity-type ON_DEMAND \
  --node-role arn:aws:iam::828879644785:role/AmazonEKSNodeRole-prod \
  --remote-access ec2SshKey=eks-prod-01,sourceSecurityGroups=sg-0459de7704ebc9276 \
  --update-config maxUnavailable=1 \
  --labels nodegroup-generation=v2 \
  --tags k8s.io/cluster-autoscaler/enabled=true,k8s.io/cluster-autoscaler/prod=present \
  --release-version 1.32.9-20260120
```

---

# PHASE 3: Verification

## Step 13: Check Nodegroup Status

```bash
# List all nodegroups
aws eks list-nodegroups --profile mnemonica --cluster-name prod

# Check individual nodegroup status
aws eks describe-nodegroup --profile mnemonica --cluster-name prod --nodegroup-name nodegroup-1a-arm-al2023 --query 'nodegroup.status'
aws eks describe-nodegroup --profile mnemonica --cluster-name prod --nodegroup-name nodegroup-1b-arm-al2023 --query 'nodegroup.status'
aws eks describe-nodegroup --profile mnemonica --cluster-name prod --nodegroup-name nodegroup-1c-arm-al2023 --query 'nodegroup.status'
```

Wait until all show `ACTIVE`.

---

## Step 14: Verify Nodes in Kubernetes

```bash
kubectl get nodes -o wide
```

You should see 9 new nodes (3 per AZ) running Amazon Linux 2023.

---

# Summary of Created Resources

| Resource Type | Name/ID | AZ |
|---------------|---------|-----|
| Public Subnet | EKS-PROD-subnet-public3-eu-west-1c | eu-west-1c |
| Elastic IP | EKS-PROD-eip-eu-west-1c | eu-west-1c |
| NAT Gateway | EKS-PROD-nat-public3-eu-west-1c | eu-west-1c |
| Private Subnet | EKS-PROD-subnet-private3-eu-west-1c | eu-west-1c |
| Route Table | EKS-PROD-rtb-private3-eu-west-1c | eu-west-1c |
| Nodegroup | nodegroup-1a-arm-al2023 | eu-west-1a |
| Nodegroup | nodegroup-1b-arm-al2023 | eu-west-1b |
| Nodegroup | nodegroup-1c-arm-al2023 | eu-west-1c |

---

# Notes

- The new nodegroups will run **alongside** the existing nodegroups
- To drain and delete the old nodegroups after verification:
  ```bash
  kubectl drain --ignore-daemonsets --delete-emptydir-data <node-name>
  aws eks delete-nodegroup --profile mnemonica --cluster-name prod --nodegroup-name <old-nodegroup-name>
  ```
- NAT Gateway incurs ongoing costs (~$0.045/hour + data processing fees)
