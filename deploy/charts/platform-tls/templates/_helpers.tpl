{{/* Pod spec shared by the restore Job and the backup CronJob: az (Workload Identity) + the Kubernetes API. */}}
{{- define "platform-tls.pod" -}}
serviceAccountName: {{ .Values.serviceAccount }}
restartPolicy: Never
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 1000
  seccompProfile: { type: RuntimeDefault }
containers:
  - name: sync
    image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
    command: ["/bin/bash", "/scripts/tls-sync.sh", {{ .mode | quote }}]
    env:
      - { name: HOME, value: /tmp }
      - { name: VAULT, value: {{ required "keyVault.name" .Values.keyVault.name | quote }} }
      - { name: CERT_ITEM, value: {{ .Values.keyVault.secretName | quote }} }    # Key Vault item name
      - { name: K8S_TLS_NAME, value: {{ .Values.secretName | quote }} }  # Kubernetes Secret name
      - { name: CERTIFICATE, value: {{ .Values.certificateName | quote }} }
      - { name: ISSUER, value: {{ .Values.issuerName | quote }} }
      - { name: HOST, value: {{ required "host" .Values.host | quote }} }
      - { name: MIN_VALID_DAYS, value: {{ .Values.restoreMinValidDays | quote }} }
    resources: {{- toYaml .Values.resources | nindent 6 }}
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities: { drop: [ALL] }
    volumeMounts:
      - { name: scripts, mountPath: /scripts, readOnly: true }
      - { name: tmp, mountPath: /tmp }
volumes:
  - name: scripts
    configMap: { name: tls-sync-script }
  - name: tmp
    emptyDir: { sizeLimit: 64Mi }
{{- end -}}
