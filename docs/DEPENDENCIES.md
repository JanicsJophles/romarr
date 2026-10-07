# Python runtime dependency inventory

Generated from the tested development environment. This is not a complete release-image SBOM: Alpine, Python, system libraries, architecture-specific wheels and development dependencies must also be inventoried for distribution. Package license metadata does not override license text included with each distribution.

| Package | Version | Reported license |
|---|---|---|
| requests | 2.34.2 | Apache-2.0 |
| certifi | 2026.7.22 | MPL-2.0 |
| charset-normalizer | 3.5.2 | MIT |
| idna | 3.20 | BSD-3-Clause |
| urllib3 | 2.8.0 | MIT |

The Docker builder copies installed distribution metadata, including package license files, with `/install` into `/usr/local`. The application LICENSE and NOTICE are separately included in `/app`. Review the final image before release.
