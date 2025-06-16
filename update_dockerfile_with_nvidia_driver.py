import os
import re
import subprocess
import json
import requests
import argparse
from bs4 import BeautifulSoup

DOCKERFILE_PATH = "Dockerfile"

def get_ami_release(cluster_name, nodegroup_name, profile, region):
    cmd = [
        "aws", "eks", "describe-nodegroup",
        "--cluster", cluster_name,
        "--nodegroup", nodegroup_name,
        "--no-cli-pager",
        "--profile", profile,
        "--region", region
    ]
    result = subprocess.run(cmd, capture_output=True, check=True, text=True)
    data = json.loads(result.stdout)
    try:
        full_release_version = data["nodegroup"]["releaseVersion"]  # e.g., "1.31.5-20250224"
        release_version = full_release_version.split("-")[-1]       # "20250224"
        k8s_version = data["nodegroup"]["version"]                  # "1.31"
        return release_version, k8s_version
    except KeyError:
        raise Exception("releaseVersion or version not found in nodegroup response")

def get_nvidia_driver_version_al2023(release_version, k8s_version):
    url = f"https://github.com/awslabs/amazon-eks-ami/releases/tag/v{release_version}"
    res = requests.get(url)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch GitHub release page: {url}")
    
    soup = BeautifulSoup(res.text, 'html.parser')

    # Locate <details> block with <summary><b>Kubernetes X.Y</b></summary>
    matching_details = None
    for detail in soup.find_all("details"):
        summary = detail.find("summary")
        if summary and summary.find("b") and f"Kubernetes {k8s_version}" in summary.find("b").text:
            matching_details = detail
            break

    if not matching_details:
        raise Exception(f"Kubernetes section {k8s_version} not found in GitHub page.")

    # Within that section, find the table with AL2023_x86_64_NVIDIA column
    tables = matching_details.find_all("table")
    target_table = None
    target_index = None

    for table in tables:
        header_row = table.find("tr")
        if not header_row:
            continue
        headers = [th.get_text(strip=True) for th in header_row.find_all("th")]
        if "AL2023_x86_64_NVIDIA" in headers:
            target_table = table
            target_index = headers.index("AL2023_x86_64_NVIDIA")
            break

    if not target_table or target_index is None:
        raise Exception("AL2023_x86_64_NVIDIA column not found in Kubernetes section")

    for row in target_table.find_all("tr")[1:]:
        cells = row.find_all("td")
        if cells and cells[0].get_text(strip=True) == "kmod-nvidia-latest-dkms":
            return cells[target_index].get_text(strip=True)

    raise Exception("kmod-nvidia-latest-dkms row not found in AL2023 table")

def format_driver_version(version):
    return f"{version.split('.')[0]}_{version}"

def find_deb_urls(driver_version_raw, os_ver):
    """
    Searches NVIDIA repo for matching .deb files using only the major.minor.rev part
    and returns both the correct NVIDIA_DRIVER_VER and a list of download URLs.
    """
    major_minor_patch = re.match(r"(\d+\.\d+\.\d+)", driver_version_raw)
    if not major_minor_patch:
        raise Exception("Could not extract major.minor.patch from driver version")
    version_base = major_minor_patch.group(1)
    major = version_base.split('.')[0]

    base_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{os_ver}/x86_64/"
    res = requests.get(base_url)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch NVIDIA repo page: {base_url}")
    
    deb_urls = []
    found_version_suffix = None

    for pkg in ['libnvidia-compute', 'libnvidia-encode', 'libnvidia-decode']:
        # Match e.g. libnvidia-encode-570_570.133.20-0ubuntu1_amd64.deb
        regex = re.compile(
            rf'{pkg}-(\d+)_({re.escape(version_base)}[-\w]*)_amd64\.deb'
        )
        match = regex.search(res.text)
        if match:
            version_suffix = match.group(2)  # e.g. 570.133.20-0ubuntu1
            deb_urls.append(base_url + match.group(0))
            found_version_suffix = version_suffix
        else:
            deb_urls.append(f"# NOT FOUND: {pkg}-{major}_{version_base}_*.deb")

    if not found_version_suffix:
        raise Exception("Could not find any matching .deb file with expected version format")

    # Construct correct NVIDIA_DRIVER_VER from actual deb filename
    formatted_driver_ver = f"{major}_{found_version_suffix}"
    return formatted_driver_ver, deb_urls

def update_dockerfile(nvidia_driver_ver):
    pattern = re.compile(r'ARG NVIDIA_DRIVER_VER=".*?"')
    with open(DOCKERFILE_PATH, 'r') as f:
        content = f.read()
    updated = pattern.sub(f'ARG NVIDIA_DRIVER_VER="{nvidia_driver_ver}"', content)
    with open(DOCKERFILE_PATH, 'w') as f:
        f.write(updated)
    print(f"Dockerfile updated with NVIDIA_DRIVER_VER={nvidia_driver_ver}")

def main(args):
    release_ver, k8s_ver = get_ami_release(args.cluster, args.nodegroup, args.profile, args.region)
    raw_driver_ver = get_nvidia_driver_version_al2023(release_ver, k8s_ver)
    formatted_driver_ver, deb_urls = find_deb_urls(raw_driver_ver, args.ubuntu)

    if args.dry_run:
        print(f"EKS AMI release version: {release_ver}")
        print(f"Kubernetes version: {k8s_ver}")
        print(f"Extracted NVIDIA driver version (raw): {raw_driver_ver}")
        print(f"Formatted NVIDIA_DRIVER_VER: {formatted_driver_ver}")
        print(f"\nMatching NVIDIA .deb packages for {args.ubuntu}:")
        for url in deb_urls:
            print(url)
    else:
        update_dockerfile(formatted_driver_ver)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update Dockerfile with NVIDIA driver version and resolve .deb URLs.")
    parser.add_argument("--cluster", required=True, help="EKS cluster name")
    parser.add_argument("--nodegroup", required=True, help="EKS nodegroup name")
    parser.add_argument("--dry-run", action="store_true", help="Print values without modifying Dockerfile")
    parser.add_argument("--profile", default=os.getenv("AWS_PROFILE", "default"), help="AWS profile (default: 'default')")
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "eu-west-1"), help="AWS region (default: 'eu-west-1')")
    parser.add_argument("--ubuntu", default="ubuntu2204", help="Ubuntu repo version (default: ubuntu2204)")
    args = parser.parse_args()
    main(args)

