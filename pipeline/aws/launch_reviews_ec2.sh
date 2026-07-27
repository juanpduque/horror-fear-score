#!/usr/bin/env bash
# Launch EC2 + start prioritized IMDb reviews fetch (Xvfb) → S3.
#
#   bash pipeline/aws/launch_reviews_ec2.sh
# Optional: LIMIT=20 bash pipeline/aws/launch_reviews_ec2.sh   # pilot
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REGION="${AWS_REGION:-us-east-1}"
KEY_NAME="${KEY_NAME:-aof-owlv2}"
KEY_FILE="${KEY_FILE:-$HOME/.ssh/aof-owlv2.pem}"
SG_ID="${SG_ID:-sg-0271740ddc4db4415}"
SUBNET_ID="${SUBNET_ID:-subnet-0206e16947d693964}"
AMI_ID="${AMI_ID:-ami-0d001f8052688dc45}"  # Ubuntu 22.04
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"
IAM_PROFILE="${IAM_PROFILE:-aof-imdb-selenium-profile}"
NAME_TAG="hfs-imdb-reviews"
BUCKET="${S3_BUCKET:-horror-fear-score-102516364259}"
PREFIX="${S3_PREFIX:-hfs}"
LIMIT="${LIMIT:-}"

export NO_PROXY='*'
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy || true

if [ ! -f "$KEY_FILE" ]; then
  echo "FATAL: missing $KEY_FILE"; exit 1
fi
if [ ! -f "$ROOT/data/gaps/gap_need_reviews_priority.csv" ]; then
  echo "FATAL: run build_reviews_priority.py first"; exit 1
fi

echo "Packing payload..."
STAGE=$(mktemp -d)
mkdir -p "$STAGE/pipeline/aws" "$STAGE/config" "$STAGE/data/gaps" "$STAGE/data/processed" "$STAGE/data/raw"
cp "$ROOT/pipeline/fetch_imdb_reviews.py" "$STAGE/pipeline/"
cp "$ROOT/pipeline/__init__.py" "$STAGE/pipeline/" 2>/dev/null || touch "$STAGE/pipeline/__init__.py"
cp "$ROOT/pipeline/aws/reviews_chain.sh" "$STAGE/pipeline/aws/"
cp "$ROOT/pipeline/aws/reviews_s3_watch.sh" "$STAGE/pipeline/aws/"
cp "$ROOT/config/paths.py" "$STAGE/config/"
cp "$ROOT/config/__init__.py" "$STAGE/config/" 2>/dev/null || touch "$STAGE/config/__init__.py"
cp "$ROOT/requirements.txt" "$STAGE/"
cp "$ROOT/data/gaps/gap_need_reviews_priority.csv" "$STAGE/data/gaps/"
[ -f "$ROOT/data/processed/legacy_review_ids.txt" ] && \
  cp "$ROOT/data/processed/legacy_review_ids.txt" "$STAGE/data/processed/" || true
tar -C "$STAGE" -czf /tmp/hfs_reviews.tgz .
rm -rf "$STAGE"

USER_DATA=$(cat <<'EOF'
#!/bin/bash
set -euo pipefail
exec > /var/log/hfs-reviews-bootstrap.log 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y xvfb unzip curl wget gnupg python3-pip python3-venv awscli

wget -q -O /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y /tmp/chrome.deb || apt-get -f install -y

mkdir -p /home/ubuntu/hfs
chown -R ubuntu:ubuntu /home/ubuntu/hfs
touch /home/ubuntu/hfs/BOOTSTRAP_OK
chown ubuntu:ubuntu /home/ubuntu/hfs/BOOTSTRAP_OK
EOF
)

echo "Launching $INSTANCE_TYPE ($AMI_ID)..."
IID=$(aws ec2 run-instances \
  --region "$REGION" \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --key-name "$KEY_NAME" \
  --security-group-ids "$SG_ID" \
  --subnet-id "$SUBNET_ID" \
  --iam-instance-profile "Name=${IAM_PROFILE}" \
  --associate-public-ip-address \
  --instance-initiated-shutdown-behavior terminate \
  --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${NAME_TAG}},{Key=Project,Value=horror-fear-score}]" \
  --user-data "$USER_DATA" \
  --query 'Instances[0].InstanceId' \
  --output text)
echo "InstanceId=$IID"
echo "$IID" > /tmp/hfs_reviews_iid.txt

aws ec2 wait instance-running --region "$REGION" --instance-ids "$IID"
IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$IID" \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "PublicIp=$IP"
echo "$IP" > /tmp/hfs_reviews_ip.txt

SSH=(ssh -i "$KEY_FILE" -o StrictHostKeyChecking=no -o ConnectTimeout=10 ubuntu@"$IP")
echo "Waiting for SSH + bootstrap..."
for i in $(seq 1 60); do
  if "${SSH[@]}" 'test -f /home/ubuntu/hfs/BOOTSTRAP_OK' 2>/dev/null; then
    echo "bootstrap ready"
    break
  fi
  sleep 10
  if [ "$i" -eq 60 ]; then
    echo "FATAL: bootstrap timeout"; exit 1
  fi
done

echo "Uploading payload..."
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no /tmp/hfs_reviews.tgz ubuntu@"$IP":/home/ubuntu/
"${SSH[@]}" "tar -xzf /home/ubuntu/hfs_reviews.tgz -C /home/ubuntu/hfs && chmod +x /home/ubuntu/hfs/pipeline/aws/*.sh"

echo "Starting chain (nohup)..."
REMOTE_ENV="export S3_BUCKET=$(printf %q "$BUCKET"); export S3_PREFIX=$(printf %q "$PREFIX"); export HFS_HOME=/home/ubuntu/hfs"
if [ -n "$LIMIT" ]; then
  REMOTE_ENV="$REMOTE_ENV; export LIMIT=$(printf %q "$LIMIT")"
fi
"${SSH[@]}" "$REMOTE_ENV; nohup bash /home/ubuntu/hfs/pipeline/aws/reviews_chain.sh >/home/ubuntu/hfs/data/raw/reviews_nohup.out 2>&1 & echo started \$!; sleep 4; tail -30 /home/ubuntu/hfs/data/raw/reviews_fetch_aws.log 2>/dev/null || tail -30 /home/ubuntu/hfs/data/raw/reviews_nohup.out || true"

echo ""
echo "=== LAUNCHED ==="
echo "id=$IID ip=$IP"
echo "bucket=s3://${BUCKET}/${PREFIX}/"
echo "ssh: ssh -i $KEY_FILE ubuntu@$IP"
echo "log:  ssh ... 'tail -f /home/ubuntu/hfs/data/raw/reviews_fetch_aws.log'"
echo "s3:   aws s3 ls s3://${BUCKET}/${PREFIX}/work/reviews/ | wc -l"
echo "stop: aws ec2 terminate-instances --region $REGION --instance-ids $IID"
