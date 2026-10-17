#!/usr/bin/env bash
# Keep the Gateway's TLS Secret and its Key Vault copy in step (no certificate data is ever printed).
#   restore  before cert-manager sees the Certificate: if the Secret is missing and Key Vault holds a
#            certificate for HOST valid for more than MIN_VALID_DAYS, recreate the Secret as cert-manager
#            would have written it, so it keeps it instead of requesting a new one from Let's Encrypt.
#   backup   if the Secret exists and differs from Key Vault (first issuance or a renewal), store it.
# Azure: the pod's Workload Identity (tls-sync), Secrets Officer on the TLS vault only.
# Kubernetes: the ServiceAccount token, allowed to get/create the one Secret in this namespace.
set -euo pipefail
MODE="${1:?restore|backup}"

SA=/var/run/secrets/kubernetes.io/serviceaccount
NS="$(cat "$SA/namespace")"
API="https://kubernetes.default.svc/api/v1/namespaces/${NS}/secrets"
k8s() { curl -sS --cacert "$SA/ca.crt" -H "Authorization: Bearer $(cat "$SA/token")" "$@"; }

az login --service-principal -u "$AZURE_CLIENT_ID" -t "$AZURE_TENANT_ID" \
  --federated-token "$(cat "$AZURE_FEDERATED_TOKEN_FILE")" --allow-no-subscriptions -o none

code="$(k8s -o /tmp/secret.json -w '%{http_code}' "${API}/${K8S_TLS_NAME}")"

case "$MODE" in
  restore)
    if [[ "$code" == 200 ]]; then echo "Secret ${K8S_TLS_NAME} exists: nothing to restore"; exit 0; fi
    [[ "$code" == 404 ]] || { echo "unexpected status ${code} reading ${K8S_TLS_NAME}"; exit 1; }
    if ! az keyvault secret show --vault-name "$VAULT" -n "$CERT_ITEM" --query value -o tsv > /tmp/kv.json 2>/dev/null; then
      echo "no certificate in Key Vault yet: cert-manager will issue one"; exit 0
    fi
    python3 - <<'EOF'
import base64, json, os, subprocess, sys
kv = json.load(open("/tmp/kv.json"))
crt = base64.b64decode(kv["tls.crt"])
open("/tmp/tls.crt", "wb").write(crt)
host, days = os.environ["HOST"], int(os.environ["MIN_VALID_DAYS"])
# The stored certificate must be for this host and outlive cert-manager's renewal window.
san = subprocess.run(["openssl", "x509", "-noout", "-ext", "subjectAltName", "-in", "/tmp/tls.crt"],
                     capture_output=True, text=True).stdout
fresh = subprocess.run(["openssl", "x509", "-noout", "-checkend", str(days * 86400), "-in", "/tmp/tls.crt"],
                       capture_output=True).returncode == 0
if f"DNS:{host}" not in san or not fresh:
    print("stored certificate is for another host or renews soon: cert-manager will issue one")
    sys.exit(0)
ann = {
    "cert-manager.io/certificate-name": os.environ["CERTIFICATE"],
    "cert-manager.io/issuer-name": os.environ["ISSUER"],
    "cert-manager.io/issuer-kind": "ClusterIssuer",
    "cert-manager.io/issuer-group": "cert-manager.io",
    "cert-manager.io/alt-names": host,
    "cert-manager.io/common-name": host,
}
secret = {
    "apiVersion": "v1", "kind": "Secret", "type": "kubernetes.io/tls",
    "metadata": {"name": os.environ["K8S_TLS_NAME"], "annotations": ann,
                 "labels": {"controller.cert-manager.io/fao": "true"}},
    "data": {"tls.crt": kv["tls.crt"], "tls.key": kv["tls.key"]},
}
json.dump(secret, open("/tmp/new-secret.json", "w"))
open("/tmp/restore", "w").write("yes")
EOF
    if [[ -f /tmp/restore ]]; then
      code="$(k8s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data @/tmp/new-secret.json "$API")"
      [[ "$code" == 201 ]] || { echo "creating ${K8S_TLS_NAME} failed: ${code}"; exit 1; }
      echo "restored ${K8S_TLS_NAME} from Key Vault"
    fi
    ;;
  backup)
    if [[ "$code" != 200 ]]; then echo "Secret ${K8S_TLS_NAME} not issued yet (${code})"; exit 0; fi
    python3 -c 'import json; d=json.load(open("/tmp/secret.json"))["data"]; json.dump({"tls.crt": d["tls.crt"], "tls.key": d["tls.key"]}, open("/tmp/new.json","w"))'
    current="$(az keyvault secret show --vault-name "$VAULT" -n "$CERT_ITEM" --query value -o tsv 2>/dev/null || true)"
    if [[ "$current" == "$(cat /tmp/new.json)" ]]; then echo "Key Vault copy is current"; exit 0; fi
    az keyvault secret set --vault-name "$VAULT" -n "$CERT_ITEM" --file /tmp/new.json \
      --content-type application/json --tags "host=${HOST}" -o none
    echo "stored ${K8S_TLS_NAME} in Key Vault"
    ;;
  *) echo "usage: tls-sync.sh restore|backup"; exit 2 ;;
esac
