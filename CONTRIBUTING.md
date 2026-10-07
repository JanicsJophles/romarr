# Contributing

This is an unpublished development fork. Preserve upstream authorship and license notices. Discuss substantial scope changes before implementation.

All changes go through a pull request. Include the problem, resulting behavior, relevant tests, and screenshots for UI changes. Passing CI and maintainer review are required before merge or release. Never commit credentials, private infrastructure details, downloaded content, or captured user conversations. Use fake fixtures and mocks.

Run the offline Python tests in an isolated environment. Network-marked tests require explicit opt-in. Do not run tests against production download clients or libraries.

CI runs only on the project-specific Atlas self-hosted runner. There is no pull_request or pull_request_target execution trigger: public fork code never runs on the private runner. Maintainers first review contributions, then place reviewed changes on a trusted same-repository branch. Pushes to trusted branches and manual workflow dispatch run checks. Restrict repository write access, isolate runners from production credentials and data, and use minimal workflow permissions. The candidate runner must be provisioned before checks can run.
