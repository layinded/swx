# Security Policy

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please report it responsibly.

**Contact:** security@swx.dev

**Do NOT** report security vulnerabilities through public GitHub issues.

## Response SLA Targets

| Severity | Initial Response | Update Frequency | Resolution Target |
|----------|-----------------|------------------|-------------------|
| Critical | 4 hours | Every 4 hours | 24 hours |
| High | 24 hours | Every 24 hours | 72 hours |
| Medium | 72 hours | Every 72 hours | 14 days |
| Low | 7 days | Every 7 days | 30 days |

## Severity Classification

- **Critical**: Remote code execution, data breach, authentication bypass, complete system compromise
- **High**: Privilege escalation, significant data exposure, denial of service with minimal resources
- **Medium**: Limited data exposure, reflected XSS, CSRF with significant impact
- **Low**: Information disclosure with minimal impact, theoretical vulnerabilities

## Escalation Matrix

1. **Security Team** (first responder) → security@swx.dev
2. **Engineering Lead** → escalated if not resolved within SLA
3. **CTO / VP Engineering** → escalated for Critical/High after 24 hours without resolution

## Supported Versions

We provide security updates for the following versions:

| Version | Supported |
|---------|-----------|
| 2.22.x | ✅ Active |
| 2.21.x | ✅ Security fixes only |
| < 2.21 | ❌ End of life |

## Key Management

See [docs/05-security/KEY_MANAGEMENT.md](docs/05-security/KEY_MANAGEMENT.md) for encryption key management procedures.

## Responsible Disclosure

We follow responsible disclosure principles:
- We acknowledge reports within 24 hours
- We provide a timeline for fixes
- We credit researchers (unless anonymity is requested)
- We do not pursue legal action against good-faith security research

## Security Controls

This application implements SOC 2 Type I controls including:
- **CC6.7**: Encryption at rest for PII fields
- **CC6.1**: Account lockout, password reset rate limiting, API key expiry, concurrent session limits, idle timeout
- **CC6.2**: Access review reports, unused role detection
- **CC6.5**: Data retention and erasure policies
- **CC7.1**: Security headers (HSTS, CSP, X-Frame-Options, X-Content-Type-Options, X-Request-ID), dependency scanning, DB connection TLS
- **CC7.2**: Comprehensive audit logging with tamper-evidence, SIEM integration
- **CC7.3**: Incident response procedures, CSP violation reporting

## Dependency Scanning

- **pip-audit**: Runs on every push and weekly on Mondays. Critical/High CVEs block merges.
- **Dependabot**: Checks for Python and GitHub Actions dependency updates weekly.
- **Hash verification**: Production builds use `pip install --require-hashes -r requirements.txt`.
- See `.github/workflows/security-scan.yml` and `.github/dependabot.yml` for configuration.