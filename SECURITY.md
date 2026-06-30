# Security Policy

## Reporting a vulnerability

If you discover a security issue, please **do not open a public issue**. Instead, report it
privately via [GitHub Security Advisories](https://github.com/PaarthSonkiya/MindBridge/security/advisories/new)
so it can be addressed before disclosure.

Please include:

- A description of the vulnerability and its impact
- Steps to reproduce
- Any suggested remediation

We aim to acknowledge reports within a few days.

## Handling of secrets

- The backend reads `ANTHROPIC_API_KEY` from the environment only; it is never logged or
  returned by the API.
- `.env` files are git-ignored. Never commit real credentials — use `.env.example` as the
  template.

## Data privacy

In offline mode no message content leaves the device. When the optional Claude path is
enabled, message content is sent to the Anthropic API for processing; operators should
enable it only where that data flow is acceptable.
