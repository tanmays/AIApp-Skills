---
name: app-store-connect
version: 1.0.0
description: Use the App Store Connect CLI (asc) to manage Apple platform apps end-to-end - upload and manage TestFlight builds, configure beta testing groups, distribute releases, handle App Store submissions, publish updates, respond to user reviews, access analytics and sales reports, inspect crash logs, update store metadata, and automate release workflows for iOS and macOS apps. Trigger this tool whenever users mention App Store Connect operations such as TestFlight, beta testers, build distribution, App Store review, release management, crash diagnostics, whats new updates, store listings, phased releases, or submitting and publishing app versions.
---

# ASC CLI

Use `asc` to manage App Store Connect from the command line. Directly run the desired asc command, assume everything is setup and works correctly. If it fails, proceed to step 0-5.

## Installation

```bash
curl -fsSL https://asccli.sh/install | bash

# To verify
asc version
```

**Updating**: re-run the same `curl` command to update.

**Step 0 - Existing Config:**
- Check for existing setup at path `/config/skills/app-store-connect/config.json`
- Verify .p8 file exists at path `/config/skills/app-store-connect/*.p8`
- If config file already exists move to step 6

## Auth Setup
### Getting an API Key (Step-by-Step Guide)

App Store Connect uses API keys for machine-to-machine access. The user needs an Apple Developer account with the appropriate role (Account Holder, Admin, or App Manager). You need to guide the user step by step in getting the required credentials to login to asc cli.

**Step 1 - Give these steps to the user:**
1. Open App Store Connect to generate a key. [App Store Connect > Users and Access > Integrations > API Keys](https://appstoreconnect.apple.com/access/integrations/api). They must sign in with their Apple Developer account
2. Click + button and give the key a name such as "Halo Agent"
3. Choose access role of either App Manager or Admin
4. Generate a .p8 key and save it to Files.app at path `iCloud Drive/Halo/<workspace>/config/skills/app-store-connect/XXXX.p8`

**Step 2**
Tell the user to let you know once the file is saved. 
Once the user confirms file saved at specified path, use bash to confirm if files exists.

**Step 3 - Collect 2 pieces of information:**
If file exists, ask user the following info one by one:
The API Keys page shows a table. Find the newly created key row:
- **Key ID** - the 10-character string in the first column (e.g. `ABC123XYZ9`)
- **Issuer ID** - shown at the top of the page (a UUID like `aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` )

Once the user gives you the required info, create a `config.json` file at `/config/skills/app-store-connect/config.json`
config.json format
```
[
  {
    "key-id": "KEY_ID",
    "issuer-id": "ISSUER_ID",
    "private-key": "XXXX.p8"
  }
]
```
Verify the config and p8 file exists, if anything is missing tell the user.

**Step 4 - Run auth login:**

```bash
asc auth login --bypass-keychain \
  --name "Halo Agent" \
  --key-id "KEY_ID" \
  --issuer-id "ISSUER_ID" \
  --private-key /config/skills/app-store-connect/XXXX.p8
```

**Step 5 - Verify:**
```bash
asc auth status --validate
```

### Detecting & Handling Auth Problems

When a user asks to do something with `asc` but auth is not set up yet, **do not run the command blindly**. Instead:

1. Run `asc auth status --validate` to check current state
2. If it returns an error or shows no credentials, tell the user:
   > "You'll need an App Store Connect API Key before `asc` can access your apps. I can guide you through the setup process step by step"
3. If the user agrees, walk through Steps 1-5 above
4. If the user already has a `.p8` file but hasn't configured auth, just run Steps 4-5
5. If `asc` is not installed, see [Installation](#installation) first

### Auth Files Location

- Config: `/config/skills/app-store-connect/config.json`
- Private Key: `/config/skills/app-store-connect/AuthKey_*.p8`

## Common Workflows

### TestFlight feedback and crashes

```bash
asc testflight feedback list --app "123456789" --paginate
asc testflight crashes list --app "123456789" --sort -createdDate --limit 10
asc testflight crashes log --submission-id "SUBMISSION_ID"
```

### Builds and distribution

```bash
asc builds upload --app "123456789" --ipa "/path/to/MyApp.ipa"
asc builds list --app "123456789" --output table
asc testflight groups list --app "123456789" --output table
```

### Release (high-level App Store publish flow)

```bash
# Optional: preview the staging plan before submission
asc release stage --app "123456789" --version "1.2.3" --build "BUILD_ID" --copy-metadata-from "1.2.2" --dry-run

# Canonical upload + attach + submit command
asc publish appstore --app "123456789" --ipa "/path/to/MyApp.ipa" --version "1.2.3" --submit --confirm

# Monitor status after submission
asc status --app "123456789" --watch
```

Lower-level submission lifecycle commands (for debugging or partial workflows):

```bash
# Canonical readiness check
asc validate --app "123456789" --version "1.2.3"
asc submit status --version-id "VERSION_ID"
asc submit cancel --version-id "VERSION_ID" --confirm
```

### Review status and blockers

```bash
asc review status --app "123456789"
asc review doctor --app "123456789"
```

### Metadata and localization

```bash
asc localizations list --app "123456789" --type app-info
asc metadata apply --app "123456789" --version "1.2.3" --dir "./metadata" --dry-run
asc metadata keywords audit --app "123456789" --version "1.2.3" --blocked-terms-file "./blocked-terms.txt"
asc apps info view --app "123456789" --output json --pretty
```

Use `asc metadata keywords audit` before `sync` or `apply` when you want an ASO-focused
review of live keyword metadata across locales. It reports duplicate phrases, repeated
terms across locales, overlap with localized app name or subtitle, byte-budget usage,
and optional blocked terms from repeated `--blocked-term` flags or a text file.

### Screenshots and media

```bash
asc screenshots plan --app "123456789" --version "1.2.3" --review-output-dir "./screenshots/review"
asc screenshots apply --app "123456789" --version "1.2.3" --review-output-dir "./screenshots/review" --confirm
asc screenshots list --version-localization "LOC_ID"
asc video-previews list --app "123456789"
```

Uploading screenshots for a single locale:

```bash
asc apps list
asc versions list --app "APP_ID"
asc localizations list --version "VERSION_ID" --output json --locale "en-US" | jsonpp
asc screenshots upload --version-localization "VERSION_LOCALIZATION_ID" --path "./screenshots/en-US" --device-type "IPHONE_65" --replace
```

### Signing and bundle IDs

```bash
asc certificates list
asc profiles list
asc bundle-ids list
```

### Workflow automation

```bash
asc workflow validate
asc workflow run --dry-run testflight_beta VERSION:1.2.3
```

### Xcode Cloud workflows and build runs

```bash
# Trigger from a pull request
asc xcode-cloud run --workflow-id "WORKFLOW_ID" --pull-request-id "PR_ID"

# Rerun from an existing build run with a clean build
asc xcode-cloud run --source-run-id "BUILD_RUN_ID" --clean

# Fetch a single build run by ID
asc xcode-cloud build-runs get --id "BUILD_RUN_ID"
```

## Commands and Reference

Use built-in help as the source of truth:

```bash
asc --help
asc <command> --help
asc <command> <subcommand> --help
```

Reference hierarchy:

- `asc --help`: authoritative command and flag surface
