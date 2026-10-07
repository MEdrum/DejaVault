# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in DejaVault, please **do not open a public issue**.

Instead, report it privately by emailing the maintainers or opening a [private security advisory](https://github.com/<owner>/<repo>/security/advisories/new) on GitHub.

Please include:

- A description of the vulnerability
- Steps to reproduce
- Affected versions
- Any suggested fix (optional)

You should receive a response within 7 days. If the issue is confirmed, a fix will be released as soon as possible, and you will be credited (if desired).

## Known Security Considerations

This service is currently **unauthenticated** — any client that can reach it can read, write, and delete memory. It is designed to run on an isolated internal network only. See [TODO.md](./TODO.md) for planned authentication work.

### Deployment Hardening

- Run behind a firewall or VPN; do not expose port 8000 to the public internet.
- The Docker containers drop all capabilities and run as a non-root user.
- Do not mount the Docker socket or host directories other than the storage volume.
- The SSH key mounted for git remote sync (if used) should be a dedicated, least-privilege key.
