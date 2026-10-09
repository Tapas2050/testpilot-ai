# SupportDesk Application Requirements Specification

## 1. Overview
SupportDesk is a web-based customer support ticket management system designed for internal support teams and administrators.

---

## 2. User Roles and Authentication

### REQ-AUTH-01: User Authentication
The system MUST provide a secure login page at `/login` allowing users to authenticate using their email address and password. Invalid credentials MUST be rejected with an appropriate error message. Authenticated sessions MUST be terminated when the user logs out via the `/logout` endpoint.

### REQ-AUTH-02: Role-Based User Access
The system supports two distinct user roles:
1. **Administrator (`admin`)**: Possesses full administrative rights across the system, including deleting tickets.
2. **Support Agent (`agent`)**: Possesses permissions to view, create, and update tickets, but is strictly restricted from administrative operations like ticket deletion.

Default demo credentials:
- Administrator: `admin@supportdesk.local`
- Support Agent: `agent@supportdesk.local`

---

## 3. Ticket Management

### REQ-TKT-01: Ticket Creation
Authenticated users (both Administrators and Support Agents) MUST be able to create a new ticket by submitting:
- Title (string, required)
- Customer Email (valid email format, required)
- Priority level (one of: Low, Medium, High; required)
- Description (text, required)

Upon successful creation, the ticket is assigned a unique numeric ID, default status `OPEN`, and the user is redirected to the ticket view page.

### REQ-TKT-02: Ticket Priority Integrity
When a ticket is created with a specified priority (`Low`, `Medium`, or `High`), the system MUST store and display the exact requested priority level without alteration. Specifically, tickets created with priority `High` MUST be persisted as `High` and displayed with a High priority indicator.

### REQ-TKT-03: Ticket View and Details
Users MUST be able to view details of any ticket at `/tickets/{id}`. The view page MUST display:
- Ticket ID and Title
- Customer Email
- Priority badge
- Current Status (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`)
- Description
- Assignee (if assigned)
- Creation timestamp

### REQ-TKT-04: Ticket Status and Assignee Updates
Authenticated users MUST be able to update ticket status to any of `OPEN`, `IN_PROGRESS`, `RESOLVED`, or `CLOSED`, and assign the ticket to an available agent or administrator.

---

## 4. Ticket Search and Filtering

### REQ-SRCH-01: Search by Ticket ID
Users MUST be able to look up a ticket by its identifier (e.g. entering `#1` or `1` in the search box). The search results table MUST return the specific ticket matching that ID.

### REQ-SRCH-02: Search by Ticket Title
Users MUST be able to search tickets by title substring (case-insensitive keyword matching).

### REQ-SRCH-03: Filter by Status
Users MUST be able to filter tickets by status (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`).

---

## 5. Security & Deletion Permissions

### REQ-SEC-01: Admin-Only Ticket Deletion
Only users with the **Administrator** role (`admin`) are permitted to delete tickets. When an Administrator submits a delete request, the ticket is permanently removed.

### REQ-SEC-02: Support Agent Deletion Prohibition
Users with the **Support Agent** role (`agent`) MUST NOT be allowed to delete tickets. Any deletion attempt by a Support Agent MUST be rejected with HTTP 403 Forbidden. Under no circumstance should a non-admin user be permitted to delete a ticket.
