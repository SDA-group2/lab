# My Lab 1 Implementation — DB-Coupled External Email Worker (State 1)

## Overview

This lab implements **State 1** of the architecture evolution:

**Strangler Fig → DB-Coupled External Worker**

The goal is to remove email sending from the MZinga monolith process and move it into an external Python worker that reads directly from MongoDB.

At the end of this lab:

- MZinga no longer sends emails in-process when the feature flag is enabled
- MZinga stores the `Communication` document and marks it as `pending`
- A Python worker polls MongoDB for pending communications
- The worker sends the email
- The worker writes the final status back to MongoDB

---

## Architecture Goal

### Before

When a `Communication` document was created in MZinga:

- the `afterChange` hook ran immediately
- recipients were resolved
- the body was serialized to HTML
- emails were sent inside the MZinga process
- the request blocked until all SMTP calls finished

### After

When a `Communication` document is created in MZinga:

- the document is stored
- status is set to `pending`
- the request returns immediately
- a separate Python worker later picks up the document
- the worker sends the email
- the worker updates the status to `sent` or `failed`

---

## What I Implemented

### 1. Added a `status` field to `Communications`

A new `status` field was added to the `Communications` collection with the following values:

- `pending`
- `processing`
- `sent`
- `failed`

The field is:

- type `select`
- shown in the admin sidebar
- read-only in the admin UI
- visible in the list view through `defaultColumns`

### 2. Added feature-flag-based external worker behavior

The following environment variable was used:

```env
COMMUNICATIONS_EXTERNAL_WORKER=true
```
