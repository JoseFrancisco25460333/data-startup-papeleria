#!/usr/bin/env bash
# Crea bucket, cola (+ cola de fallidos) y roles de IAM de minimo privilegio para E2.
# Requiere AWS CLI v2 configurado con TU USUARIO IAM (no la cuenta raiz).
#   source infra/aws/variables.env && bash infra/aws/setup.sh
# NOTA: pensado para correrse una sola vez; si un recurso ya existe, el comando falla
# con un mensaje claro y puedes seguir con el siguiente paso a mano.
set -euo pipefail
: "${AWS_REGION:?}" "${ACCOUNT_ID:?}" "${BUCKET:?}" "${QUEUE_NAME:?}" "${DLQ_NAME:?}" "${ROLE_EC2:?}" "${ROLE_WORKER:?}"
cd "$(dirname "$0")"
export AWS_DEFAULT_REGION="$AWS_REGION"

echo "== 1/4 Bucket S3 (data lake: raw/ y clean/)"
if [ "$AWS_REGION" = "us-east-1" ]; then
  aws s3api create-bucket --bucket "$BUCKET"
else
  aws s3api create-bucket --bucket "$BUCKET" --create-bucket-configuration "LocationConstraint=$AWS_REGION"
fi
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration file://policies/bucket-sin-publico.json
aws s3api put-bucket-encryption --bucket "$BUCKET" --server-side-encryption-configuration \
  '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-object --bucket "$BUCKET" --key raw/
aws s3api put-object --bucket "$BUCKET" --key clean/

echo "== 2/4 Cola SQS + cola de mensajes fallidos (DLQ)"
DLQ_URL=$(aws sqs create-queue --queue-name "$DLQ_NAME" --query QueueUrl --output text)
DLQ_ARN=$(aws sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
# VisibilityTimeout 120 s: tiempo que el worker tiene para procesar antes de que el mensaje reaparezca (reintento)
# maxReceiveCount 3: al tercer intento fallido el mensaje pasa a la DLQ
ATTR=$(python3 - <<PY
import json
print(json.dumps({"VisibilityTimeout": "120", "ReceiveMessageWaitTimeSeconds": "20", "SqsManagedSseEnabled": "true",
  "RedrivePolicy": json.dumps({"deadLetterTargetArn": "$DLQ_ARN", "maxReceiveCount": "3"})}))
PY
)
QUEUE_URL=$(aws sqs create-queue --queue-name "$QUEUE_NAME" --attributes "$ATTR" --query QueueUrl --output text)
QUEUE_ARN=$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

echo "== 3/4 Politicas (se rellenan los marcadores __X__)"
mkdir -p /tmp/papeleria-policies
for f in ec2-ingesta-policy worker-policy worker-trust ec2-trust tablero-lectura-policy; do
  sed -e "s|__BUCKET__|$BUCKET|g" -e "s|__QUEUE_ARN__|$QUEUE_ARN|g" -e "s|__ACCOUNT_ID__|$ACCOUNT_ID|g" \
      -e "s|__ROLE_WORKER__|$ROLE_WORKER|g" -e "s|__ROLE_EC2__|$ROLE_EC2|g" "policies/$f.json" > "/tmp/papeleria-policies/$f.json"
done

echo "== 4/4 Roles de IAM: VM de ingesta y worker (minimo privilegio)"
aws iam create-role --role-name "$ROLE_EC2" --assume-role-policy-document file:///tmp/papeleria-policies/ec2-trust.json >/dev/null
aws iam put-role-policy --role-name "$ROLE_EC2" --policy-name ingesta --policy-document file:///tmp/papeleria-policies/ec2-ingesta-policy.json
aws iam create-instance-profile --instance-profile-name "$ROLE_EC2" >/dev/null
aws iam add-role-to-instance-profile --instance-profile-name "$ROLE_EC2" --role-name "$ROLE_EC2"
sleep 10   # IAM tarda unos segundos en propagar el rol antes de poder nombrarlo como principal
aws iam create-role --role-name "$ROLE_WORKER" --assume-role-policy-document file:///tmp/papeleria-policies/worker-trust.json >/dev/null
aws iam put-role-policy --role-name "$ROLE_WORKER" --policy-name worker --policy-document file:///tmp/papeleria-policies/worker-policy.json
aws iam create-policy --policy-name papeleria-tablero-lectura --policy-document file:///tmp/papeleria-policies/tablero-lectura-policy.json >/dev/null || true

cat <<OUT

Listo. Guarda estos valores (NO son secretos, pero tampoco los subas con claves):
  BUCKET=$BUCKET
  QUEUE_URL=$QUEUE_URL
  DLQ_URL=$DLQ_URL
Siguientes pasos: sube el historico, lanza la EC2 con el perfil '$ROLE_EC2' y despliega (docs/E2-cimientos.md, seccion 9).
OUT
