ServiceNow Business Rule: Auto-resolve incident when comment contains marker

Purpose
- Automatically set an incident to Resolved (state = 6) when an agent/API adds a comment
  containing a specific marker text (e.g., "Resolved via MCP automation"). This avoids
  requiring elevated API user roles to change `state` directly.

Placement
- In ServiceNow: System Definition > Business Rules > New

Fields (recommended values)
- Name: Auto Resolve on Comment Marker
- Table: incident
- Advanced: checked
- When: before
- Insert: false
- Update: true
- Order: 100
- Active: true
- Condition: (leave blank) — the script will check the marker

Script (paste into the Advanced > Script box):

// Business Rule script: requires u_auto_resolve == true, the comment MARKER,
// and a non-empty called_id before auto-resolving. It clears the flag after
// resolving to avoid re-triggering.
(function executeRule(current, previous /*null when async*/) {
  var MARKER = 'Resolved via MCP automation';

  // Only proceed when the custom flag u_auto_resolve is true
  if (!current.u_auto_resolve) return;

  // Require the called_id field to be present/non-empty before allowing auto-resolve
  if (!current.called_id || String(current.called_id).trim() === '') return;

  // Only run when comments were updated and include the marker
  if (!current.comments || String(current.comments).indexOf(MARKER) === -1) return;

  // If already resolved, clear the flag and skip
  if (current.state == 6) {
    current.u_auto_resolve = false;
    return;
  }

  // Set resolved fields
  current.state = 6; // Resolved
  current.close_notes = 'Automatically resolved: ' + MARKER + '\nCalled ID: ' + current.called_id;
  current.resolved_by = gs.getUserID();
  current.resolved_at = gs.nowDateTime();

  // Clear the flag so it doesn't fire again
  current.u_auto_resolve = false;
})(current, previous);

Notes
- The marker string must match exactly what the automation writes into `comments`.
- If your environment uses different incident state values, adjust `state = 6` accordingly.
- Test this on a non-production instance first.

How to use with the existing scripts
1. Install this Business Rule in your ServiceNow instance.
2. Re-run the comment-patching script (`apply_comments_and_create_kb.py`) or use the MCP/REST calls
   to add a comment containing the marker `Resolved via MCP automation`.
3. The Business Rule will run on update and mark the incident Resolved automatically.

Security & ACLs
- This pattern avoids changing API roles. The Business Rule runs with system context (subject to
  your ServiceNow instance configuration) — ensure you review ACLs and test appropriately.
