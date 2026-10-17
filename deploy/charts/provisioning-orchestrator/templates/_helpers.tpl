{{/*
Public host on the shared Gateway, from .Values.dns.mode:
  auto    (default) read from the Gateway at deploy time: its idp.io/public-host annotation (the Azure
          DNS label 30-cluster-config sets, the same across provisions), else platform-hooks.<gateway-ip>.nip.io
  domain  platform-hooks.<dns.domain>, an own domain (e.g. an Azure DNS zone)
  host    dns.host as given (Backstage's public host: dns.backstageHost, default the same)
helm template has no cluster to read, so auto falls back to platform-hooks.localhost there.
*/}}
{{- define "provisioning-orchestrator.hostFor" -}}
{{- $d := .ctx.Values.dns -}}
{{- if eq $d.mode "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .ctx.Values.hooks.gateway.namespace .ctx.Values.hooks.gateway.name | default dict -}}
{{- $addresses := dig "status" "addresses" list $gw -}}
{{- $host := dig "metadata" "annotations" "idp.io/public-host" "" $gw -}}
{{- if and (not $host) $addresses }}{{ $host = printf "%s.%s.nip.io" .prefix (index $addresses 0).value }}{{ end -}}
{{- $host | default (printf "%s.localhost" .prefix) -}}
{{- else if eq $d.mode "domain" -}}
{{- printf "%s.%s" .prefix (required "dns.domain" $d.domain) -}}
{{- else if eq $d.mode "host" -}}
{{- if eq .prefix "backstage" }}{{ $d.backstageHost | default $d.host }}{{ else }}{{ required "dns.host" $d.host }}{{ end -}}
{{- else -}}
{{- fail "dns.mode must be auto, domain or host" -}}
{{- end -}}
{{- end -}}

{{- define "provisioning-orchestrator.host" -}}
{{- include "provisioning-orchestrator.hostFor" (dict "ctx" . "prefix" "platform-hooks") -}}
{{- end -}}

{{/* Backstage's public URL (its chart resolves the same way), for links on the Provisioning tab. */}}
{{- define "provisioning-orchestrator.backstageUrl" -}}
{{ include "provisioning-orchestrator.scheme" . }}://{{ include "provisioning-orchestrator.hostFor" (dict "ctx" . "prefix" "backstage") }}
{{- end -}}

{{- define "provisioning-orchestrator.url" -}}
{{ include "provisioning-orchestrator.scheme" . }}://{{ include "provisioning-orchestrator.host" . }}
{{- end -}}

{{/*
TLS on the public host, from .Values.dns.tls: true/false as given, or "auto" (default): read the Gateway at
deploy time and use https once its "https" listener is Programmed with a resolved certificate (cert-manager
has issued it). helm template has no cluster to read, so auto means http there. Renders "true" or "false".
*/}}
{{- define "provisioning-orchestrator.tls" -}}
{{- $t := .Values.dns.tls -}}
{{- if kindIs "bool" $t -}}
{{- $t -}}
{{- else if eq (toString $t) "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .Values.hooks.gateway.namespace .Values.hooks.gateway.name | default dict -}}
{{- $on := false -}}
{{- range (dig "status" "listeners" list $gw) -}}
{{- if eq .name "https" -}}
{{- $ok := 0 -}}
{{- range .conditions -}}
{{- if and (has .type (list "Programmed" "ResolvedRefs")) (eq .status "True") }}{{ $ok = add1 $ok }}{{ end -}}
{{- end -}}
{{- if eq $ok 2 }}{{ $on = true }}{{ end -}}
{{- end -}}
{{- end -}}
{{- $on -}}
{{- else -}}
{{- fail "dns.tls must be auto, true or false" -}}
{{- end -}}
{{- end -}}

{{- define "provisioning-orchestrator.scheme" -}}
{{- ternary "https" "http" (eq (include "provisioning-orchestrator.tls" .) "true") -}}
{{- end -}}
