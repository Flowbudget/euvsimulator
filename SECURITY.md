# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.2.x   | :white_check_mark: |
| < 2.2   | :x:                |

## Reporting a Vulnerability

euvsimulator is a simulation library with a local REST/GUI server. If you find a
security problem, please report it privately.

**Do not report security vulnerabilities through public GitHub issues.**

Use GitHub's private vulnerability reporting for this repository:
[Report a vulnerability](https://github.com/Flowbudget/euvsimulator/security/advisories/new)
(Security tab → "Report a vulnerability"). Please include:

- A description of the vulnerability
- Steps to reproduce the issue
- The version(s) of euvsimulator affected
- Any potential impact you have identified

### What to expect

This project is maintained by one person in their spare time.

- Receipt is acknowledged within about one week.
- A fix is coordinated with you before disclosure, with a timeline that depends on severity.
- You are credited in the advisory unless you ask not to be.

## Disclosure Policy

1. Confirm receipt and reproduce the issue.
2. Prepare a fix and a release.
3. Publish a GitHub security advisory and credit the reporter (with consent).

Note that `euv serve` binds to all interfaces (0.0.0.0) by default and has no
authentication; it is meant for a local machine or a trusted network. Do not
expose it to the internet.

Thank you for helping keep euvsimulator and its users safe.
