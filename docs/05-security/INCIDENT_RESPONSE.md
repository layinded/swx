# Incident Response Runbook

## Incident Classification

| Level | Description | Example |
|-------|-------------|---------|
| SEV-1 | Critical | Data breach, auth bypass, complete service outage |
| SEV-2 | High | Privilege escalation, partial data exposure, major feature outage |
| SEV-3 | Medium | Limited data exposure, reflected XSS, degraded performance |
| SEV-4 | Low | Information disclosure, theoretical vulnerability, minor bugs |

## Response Playbooks

### SEV-1: Critical Incident

1. **T+0**: Acknowledge report, assign incident commander
2. **T+15min**: Assemble response team, begin containment
3. **T+1hr**: Assess scope, communicate status to stakeholders
4. **T+4hr**: Deploy fix or mitigation, verify containment
5. **T+24hr**: Complete remediation, begin post-incident review

### SEV-2: High Incident

1. **T+0**: Acknowledge report, assign incident commander
2. **T+1hr**: Begin investigation, assess impact
3. **T+4hr**: Deploy fix or mitigation
4. **T+72hr**: Complete remediation, post-incident review

### SEV-3: Medium Incident

1. **T+0**: Acknowledge report
2. **T+24hr**: Investigate and triage
3. **T+14 days**: Deploy fix, close incident

### SEV-4: Low Incident

1. **T+0**: Acknowledge report
2. **T+7 days**: Investigate and triage
3. **T+30 days**: Deploy fix if applicable

## Communication Templates

### Internal Notification

```
INCIDENT [SEV-N] - [Title]
Status: [Investigating/Contained/Resolved]
Impact: [Description of affected systems/users]
Timeline: [Key timestamps]
Current Actions: [What's being done]
Next Update: [When]
```

### External Notification (if required)

```
We are aware of [issue description]. Our team is actively working on [actions].
[Impact description]. We will provide updates every [interval].
```

## CSP Violation Response

CSP violations are logged as `security.csp_violation` audit events. To review:

1. Query audit logs: `GET /admin/compliance/access-review` or `GET /admin/audit/logs?action=security.csp_violation`
2. Analyze the `violated_directive` and `document_uri` in the audit event context
3. If legitimate violation: update CSP policy in `SecurityHeadersConfig.csp_api`
4. If attack attempt: escalate per severity matrix

## Post-Incident Review

After every SEV-1 or SEV-2 incident:

1. Schedule review within 48 hours
2. Document: timeline, root cause, impact, remediation
3. Identify: what worked, what didn't, what needs improvement
4. Create: action items with owners and deadlines
5. Update: this runbook and related procedures

## Key Contacts

| Role | Contact |
|------|---------|
| Security Team | security@swx.dev |
| Engineering Lead | eng-lead@swx.dev |
| On-Call Engineer | See PagerDuty rotation |