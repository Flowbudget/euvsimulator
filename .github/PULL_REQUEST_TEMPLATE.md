---
name: Pull Request
description: Submit a pull request for OpEnUV
title: "[PR]: "
labels: ["triage"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for contributing to OpEnUV! Please fill out the following information.
  - type: checkboxes
    id: checklist
    attributes:
      label: Checklist
      options:
        - label: I have read the CONTRIBUTING.md guide
          required: true
        - label: I have run `pytest tests/ -x` locally and all tests pass
          required: true
        - label: I have run `ruff check src/ tests/` and `ruff format --check src/ tests/`
          required: true
        - label: I have added/updated tests for my changes
          required: true
        - label: I have updated documentation if needed (docstrings, README, etc.)
          required: false
        - label: This PR is linked to an existing issue
          required: false
  - type: dropdown
    id: type
    attributes:
      label: Type of change
      options:
        - Bug fix (non-breaking change which fixes an issue)
        - New feature (non-breaking change which adds functionality)
        - Breaking change (fix or feature that would cause existing functionality to not work as expected)
        - Documentation update
        - Refactoring (no functional changes)
        - Performance improvement
        - CI/CD changes
    validations:
      required: true
  - type: textarea
    id: description
    attributes:
      label: Description
      description: What does this PR do? Why is it needed?
      placeholder: |
        Fixes #123
        
        This PR adds...
  - type: textarea
    id: testing
    attributes:
      label: Testing
      description: How did you test this change? Include commands and output if relevant.
      placeholder: |
        - Ran `pytest tests/test_pipeline.py -x -v` - all 42 tests pass
        - Ran `euv simulate --period=64 --cd=32 --dose=20` - CD = 31.8 nm (expected ~32 nm)
        - Verified no regressions with `pytest tests/ -x`
    validations:
      required: true
  - type: textarea
    id: breaking
    attributes:
      label: Breaking changes
      description: If this is a breaking change, describe what breaks and how users should migrate.
      placeholder: "No breaking changes" or "This changes the API for SimulationConfig.resist_model..."
  - type: checkboxes
    id: docs
    attributes:
      label: Documentation
      options:
        - label: I have updated relevant docstrings
        - label: I have updated README.md if needed
        - label: I have updated COMPLETION_PLAN.md if this completes a milestone
        - label: I have added an entry to CHANGELOG.md