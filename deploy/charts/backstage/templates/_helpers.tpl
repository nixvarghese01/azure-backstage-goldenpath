{{/*
Public host on the shared Gateway, from .Values.dns.mode:
  auto    (default) read from the Gateway at deploy time: its idp.io/public-host annotation (the Azure
          DNS label 30-cluster-config sets, the same across provisions), else backstage.<gateway-ip>.nip.io
  domain  backstage.<dns.domain>, an own domain (e.g. an Azure DNS zone)
  host    dns.host as given (the orchestrator hooks: dns.hooksHost, default the same host)
helm template has no cluster to read, so auto falls back to backstage.localhost there.
*/}}
{{- define "backstage.hostFor" -}}
{{- $d := .ctx.Values.dns -}}
{{- if eq $d.mode "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .ctx.Values.gateway.namespace .ctx.Values.gateway.name | default dict -}}
{{- $addresses := dig "status" "addresses" list $gw -}}
{{- $host := dig "metadata" "annotations" "idp.io/public-host" "" $gw -}}
{{- if and (not $host) $addresses }}{{ $host = printf "%s.%s.nip.io" .prefix (index $addresses 0).value }}{{ end -}}
{{- $host | default (printf "%s.localhost" .prefix) -}}
{{- else if eq $d.mode "domain" -}}
{{- printf "%s.%s" .prefix (required "dns.domain" $d.domain) -}}
{{- else if eq $d.mode "host" -}}
{{- if eq .prefix "backstage" }}{{ required "dns.host" $d.host }}{{ else }}{{ $d.hooksHost | default $d.host }}{{ end -}}
{{- else -}}
{{- fail "dns.mode must be auto, domain or host" -}}
{{- end -}}
{{- end -}}

{{- define "backstage.host" -}}
{{- include "backstage.hostFor" (dict "ctx" . "prefix" "backstage") -}}
{{- end -}}

{{/* The orchestrator's public hooks host (its chart resolves the same way): generated repos post callbacks there. */}}
{{- define "backstage.callbackUrl" -}}
{{ include "backstage.scheme" . }}://{{ include "backstage.hostFor" (dict "ctx" . "prefix" "platform-hooks") }}
{{- end -}}

{{- define "backstage.url" -}}
{{ include "backstage.scheme" . }}://{{ include "backstage.host" . }}
{{- end -}}

{{/* Overrides of app-config.production.yaml that depend on this release's values. */}}
{{- define "backstage.appConfig" -}}
{{- $tls := eq (include "backstage.tls" .) "true" -}}
{{- if and $tls (not .Values.database.inCluster) -}}
{}
{{- else -}}
backend:
  {{- if not $tls }}
  # Served over plain HTTP: the default CSP's upgrade-insecure-requests would make browsers fetch
  # the frontend's scripts over https, which nothing serves, and the page stays blank.
  csp:
    upgrade-insecure-requests: false
  {{- end }}
  {{- if .Values.database.inCluster }}
  # dev: PostgreSQL inside the cluster (deploy/charts/postgres): in-cluster host and login role, no
  # TLS on the pod network. The password stays the production one: /mnt/secrets/backstage-db-password,
  # from Key Vault through the CSI driver.
  database:
    connection:
      host: postgres
      user: backstage
      ssl: false
  {{- end }}
{{- end -}}
{{- end -}}

{{/*
TLS on the public host, from .Values.dns.tls: true/false as given, or "auto" (default): read the Gateway at
deploy time and use https once its "https" listener is Programmed with a resolved certificate (cert-manager
has issued it). helm template has no cluster to read, so auto means http there. Renders "true" or "false".
*/}}
{{- define "backstage.tls" -}}
{{- $t := .Values.dns.tls -}}
{{- if kindIs "bool" $t -}}
{{- $t -}}
{{- else if eq (toString $t) "auto" -}}
{{- $gw := lookup "gateway.networking.k8s.io/v1" "Gateway" .Values.gateway.namespace .Values.gateway.name | default dict -}}
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

{{- define "backstage.scheme" -}}
{{- ternary "https" "http" (eq (include "backstage.tls" .) "true") -}}
{{- end -}}
