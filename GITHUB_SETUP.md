# GitHub Issues Setup Guide

This guide will help you authenticate with GitHub and create issues from the comprehensive TODO list.

## Quick Start

### Option 1: Interactive Authentication (Easiest)

```bash
# Run the interactive login
gh auth login

# Follow the prompts:
# 1. Select: GitHub.com
# 2. Select: HTTPS
# 3. Select: Login with a web browser
# 4. Copy the one-time code shown
# 5. Press Enter to open browser
# 6. Paste code and authorize

# Then create the issues
./scripts/create-github-issues.sh
```

### Option 2: Using a Personal Access Token

1. **Create a GitHub Personal Access Token:**
   - Go to: https://github.com/settings/tokens/new
   - Name: "KnowledgeBaseAI Issue Creation"
   - Expiration: 30 days (or as needed)
   - Scopes required:
     - ✓ `repo` (Full control of private repositories)
     - ✓ `workflow` (if you want to update workflows)

2. **Authenticate with the token:**
```bash
# Export token (replace with your token)
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"

# Login with token
echo $GITHUB_TOKEN | gh auth login --with-token

# Verify authentication
gh auth status

# Create issues
./scripts/create-github-issues.sh
```

### Option 3: SSH Authentication (if you have SSH keys)

```bash
# If your SSH keys are already set up for GitHub:
gh auth login

# Select:
# 1. GitHub.com
# 2. SSH
# 3. Skip upload (if key already exists)

# Then create issues
./scripts/create-github-issues.sh
```

## What the Script Does

The `create-github-issues.sh` script will:

1. ✓ Create priority labels (P0-critical, P1-high, P2-medium, P3-low)
2. ✓ Create category labels (security, performance, bug, etc.)
3. ✓ Create milestones for implementation phases
4. ✓ Create GitHub issues with:
   - Detailed descriptions
   - Code examples
   - Fix instructions
   - Time estimates
   - Proper labels and milestones

## Issues to be Created

### P0 - Critical (8 issues)
- SEC-001: Exposed Secrets in Version Control
- SEC-002: CORS Misconfiguration
- SEC-003: PostgreSQL Trust Authentication
- SEC-004: Missing Health Checks
- DATA-001: No Backup Strategy
- BUG-001: Neo4j Driver Lifecycle Bug
- BUG-002: React EditPage Broken
- And more...

### P1 - High (Sample created)
- PERF-001: Inefficient Roadmap Query
- PERF-002: LLM Caching
- DATA-002: Connection Pooling
- And more...

### P2 - Medium (Sample created)
- CODE-001: Bare Exception Handlers
- TEST-001: Test Coverage
- And more...

## Troubleshooting

### "gh: command not found"
The script should have installed gh CLI, but if not:
```bash
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | \
  sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \
  https://cli.github.com/packages stable main" | \
  sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

sudo apt update && sudo apt install gh -y
```

### "Authentication required"
Make sure you've completed one of the authentication options above.

```bash
# Check authentication status
gh auth status

# If not authenticated, run:
gh auth login
```

### "Permission denied" error
The script needs execute permissions:
```bash
chmod +x scripts/create-github-issues.sh
```

### "API rate limit exceeded"
GitHub has rate limits. If creating many issues:
- Authenticated requests: 5000/hour
- If you hit the limit, wait an hour or use a different token

### "Label already exists" warnings
These are normal and can be ignored. The script tries to create labels but won't fail if they already exist.

## Verifying Issues Were Created

```bash
# List recent issues
gh issue list --repo XTeam-Pro/KnowledgeBaseAI --limit 20

# View a specific issue
gh issue view 1 --repo XTeam-Pro/KnowledgeBaseAI

# Or visit in browser
gh issue list --repo XTeam-Pro/KnowledgeBaseAI --web
```

## Customizing the Script

To create ALL issues (including P2 and P3), edit the script:

```bash
nano scripts/create-github-issues.sh

# Add more issue creation blocks following the same pattern
# Example:
cat > "$ISSUES_DIR/your-issue.md" << 'EOF'
## Problem
...
EOF

create_issue "[ISSUE-XXX] Title" \
    "$ISSUES_DIR/your-issue.md" \
    "priority:P2-medium,technical-debt" \
    "Month 2: Code Quality & Testing"
```

## Manual Issue Creation

If you prefer to create issues manually, all issue bodies are saved in `./github-issues/` directory:

```bash
ls -la github-issues/
# sec-001.md, sec-002.md, etc.

# View an issue body
cat github-issues/sec-001.md

# Create manually in GitHub UI and copy/paste the content
```

## Next Steps

After creating issues:

1. **Review and prioritize** - Visit the issues page and adjust priorities if needed
2. **Assign owners** - Assign issues to team members
3. **Create project board** - Organize issues in a Kanban board
4. **Start with P0** - Begin with critical security fixes

```bash
# Create a project board (optional)
gh project create --owner XTeam-Pro --title "Technical Debt Cleanup"
```

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify GitHub CLI is installed: `gh --version`
3. Check authentication: `gh auth status`
4. Review script output for error messages

## Security Note

⚠️ Never commit GitHub tokens to the repository!

If you used a token:
```bash
# Unset the token after use
unset GITHUB_TOKEN

# Or revoke it at:
# https://github.com/settings/tokens
```
