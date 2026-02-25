# Meeting Task Automation Setup Guide

This guide walks you through setting up the three Microsoft 365 components needed for the meeting task automation Power Automate flows.

---

## Component 1: Excel File (UserMapping.xlsx) — DONE

The file `UserMapping.xlsx` has been pre-created with:
- **Table name**: `UserMap`
- **Columns**: Name | Email
- **7 team members** with placeholder emails

### To upload to OneDrive:
1. Go to [OneDrive](https://onedrive.live.com)
2. Click **Upload** → **Files**
3. Select `UserMapping.xlsx` from this folder
4. Once uploaded, open it in Excel Online to verify the table is intact
5. **Copy the URL** from the address bar — you'll need this for Power Automate

> **Note**: Update the email addresses with real ones when ready.

---

## Component 2: Planner Board

### Steps:
1. Go to [Microsoft Planner](https://tasks.office.com)
2. Click **New Plan**
3. Name it: **Meeting Tasks**
4. Create these buckets (in order):
   - `To Do` (usually exists by default)
   - `In Progress`
   - `Blocked`
   - `Completed`
5. **Copy the Planner URL** from the address bar

---

## Component 3: Microsoft Form (Task Update)

### Steps:
1. Go to [Microsoft Forms](https://forms.office.com)
2. Click **New Form**
3. Set the title: **Task Update**
4. Set the description: `Submit a status update for your assigned task`

### Add 3 Questions:

| # | Question Text | Type | Required | Details |
|---|--------------|------|----------|---------|
| 1 | Task Name | Text (Short) | Yes | — |
| 2 | Status | Choice | Yes | Options: `In Progress`, `Blocked`, `Completed` |
| 3 | Update Notes | Text (Long) | Yes | Placeholder: `Describe what you've done, any blockers, or next steps` |

### Get the Form Field ID (Critical):
1. Click the **⋯** (three dots) menu at top right
2. Select **Get pre-filled URL** (or "Prefill")
3. In the Task Name field, type: `TEST`
4. Click **Get link** or **Copy link**
5. The URL will look like:
   ```
   https://forms.office.com/Pages/ResponsePage.aspx?id=v4j5...&r48294=TEST
   ```
6. The part after `&r` and before `=TEST` is your **Field ID** (e.g., `r48294`)
7. **Save this Field ID** — you need it for Power Automate smart links

---

## Summary of What You'll Need for Power Automate

| Item | Where to Find It |
|------|-----------------|
| Excel File URL | OneDrive address bar after uploading `UserMapping.xlsx` |
| Excel Table Name | `UserMap` (already set) |
| Planner Board URL | Planner address bar after creating "Meeting Tasks" |
| Form URL | Forms share link |
| Form Field ID | From the pre-filled URL (e.g., `r48294`) |

---

## Quick Reference: Team Members

| Name | Email |
|------|-------|
| Chris Greer | chris.greer@flex.com |
| Mike Keane | mike.keane@flex.com |
| Tess York | tess.york@flex.com |
| Shawna Wass | shawna.wass@flex.com |
| Mike Sun | mike.sun@flex.com |
| Kim Jordan | kim.jordan@flex.com |
| Tia Waldron | tia.waldron@flex.com |

---

## Next Steps

Once you have all 5 items above, you're ready to build the Power Automate flows to:
1. Parse meeting transcripts for action items
2. Create Planner tasks automatically
3. Send personalized task update form links to assignees
