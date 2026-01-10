{{/*
Expand the name of the chart.
*/}}
{{- define "payment-transformer.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "payment-transformer.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "payment-transformer.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "payment-transformer.labels" -}}
helm.sh/chart: {{ include "payment-transformer.chart" . }}
{{ include "payment-transformer.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "payment-transformer.selectorLabels" -}}
app.kubernetes.io/name: {{ include "payment-transformer.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- if .Values.provider.name }}
app.kubernetes.io/component: {{ .Values.provider.name }}-transformer
{{- end }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "payment-transformer.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "payment-transformer.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
