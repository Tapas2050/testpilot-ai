"""SupportDesk demo web application with defect injection toggle."""

import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import get_settings
from app.database import get_connection, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(seed=True)
    yield


app = FastAPI(
    title="SupportDesk",
    description="Customer support ticket system with configurable QA defect toggle",
    version="1.0.0",
    lifespan=lifespan,
)


def get_current_user_from_req(request: Request) -> Optional[dict]:
    session_id = request.cookies.get("session_id")
    if not session_id:
        # Check Authorization header bearer token
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_id = auth_header.split(" ")[1]

    if not session_id:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.email, u.role
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_id = ?
    """, (session_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return dict(row)
    return None


def require_auth(request: Request) -> dict:
    user = get_current_user_from_req(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


# HTML Templates helper
def render_page(title: str, content: str, user: Optional[dict] = None) -> HTMLResponse:
    user_nav = ""
    if user:
        user_nav = f"""
        <div style="display: flex; align-items: center; gap: 16px;">
            <span id="current-user-email" style="font-size: 13px; color: #64748B;">
                {user['email']} (<strong id="current-user-role">{user['role']}</strong>)
            </span>
            <a href="/logout" id="logout-btn" style="color: #DC2626; text-decoration: none; font-size: 13px; font-weight: 500;">Logout</a>
        </div>
        """
    else:
        user_nav = '<a href="/login" id="nav-login-btn" style="color: #4F46E5; text-decoration: none; font-size: 13px;">Login</a>'

    settings = get_settings()
    defect_banner = ""
    if settings.defects_enabled:
        defect_banner = '<div style="background: #FEE2E2; color: #991B1B; padding: 6px 16px; font-size: 12px; font-weight: 600; text-align: center;">DEFECT SWITCH ACTIVE (SUPPORTDESK_DEFECTS=on)</div>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - SupportDesk</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #F8FAFC; color: #0F172A; line-height: 1.5; }}
        header {{ background: #FFFFFF; border-bottom: 1px solid #E2E8F0; padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; }}
        .container {{ max-width: 1000px; margin: 24px auto; padding: 0 16px; }}
        .card {{ background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 24px; margin-bottom: 24px; }}
        .btn {{ display: inline-block; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; text-decoration: none; border: 1px solid transparent; }}
        .btn-primary {{ background: #4F46E5; color: #FFFFFF; border-color: #4F46E5; }}
        .btn-danger {{ background: #DC2626; color: #FFFFFF; border-color: #DC2626; }}
        .btn-secondary {{ background: #FFFFFF; color: #0F172A; border-color: #CBD5E1; }}
        .form-group {{ margin-bottom: 16px; }}
        .form-label {{ display: block; font-size: 13px; font-weight: 500; margin-bottom: 6px; }}
        .form-input, .form-select, .form-textarea {{ width: 100%; padding: 8px 12px; border: 1px solid #CBD5E1; border-radius: 6px; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 16px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #E2E8F0; font-size: 13px; }}
        th {{ background: #F8FAFC; font-weight: 600; color: #64748B; }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }}
        .badge-open {{ background: #DBEAFE; color: #1D4ED8; }}
        .badge-progress {{ background: #FEF3C7; color: #B45309; }}
        .badge-resolved {{ background: #DCFCE7; color: #15803D; }}
        .badge-closed {{ background: #F1F5F9; color: #475569; }}
        .badge-high {{ background: #FEE2E2; color: #B91C1C; }}
        .badge-med {{ background: #FFEDD5; color: #C2410C; }}
        .badge-low {{ background: #F1F5F9; color: #475569; }}
    </style>
</head>
<body>
    {defect_banner}
    <header>
        <div style="display: flex; align-items: center; gap: 12px;">
            <a href="/" style="font-weight: 700; font-size: 18px; color: #4F46E5; text-decoration: none;">SupportDesk</a>
            <span style="font-size: 12px; background: #EEF2FF; color: #4F46E5; padding: 2px 8px; border-radius: 12px; font-weight: 600;">Demo Target</span>
        </div>
        {user_nav}
    </header>
    <main class="container">
        {content}
    </main>
</body>
</html>
"""
    return HTMLResponse(content=html)


@app.get("/")
def index(request: Request):
    user = get_current_user_from_req(request)
    if not user:
        return RedirectResponse(url="/login")
    return RedirectResponse(url="/tickets")


@app.get("/login")
def login_page(request: Request, error: Optional[str] = None):
    err_box = f'<div style="background: #FEE2E2; color: #991B1B; padding: 8px 12px; border-radius: 4px; margin-bottom: 16px; font-size: 13px;" id="login-error">{error}</div>' if error else ""
    content = f"""
    <div style="max-width: 400px; margin: 40px auto;" class="card">
        <h2 style="margin-bottom: 8px;">Sign In to SupportDesk</h2>
        <p style="color: #64748B; font-size: 13px; margin-bottom: 20px;">Use demo administrator or agent credentials</p>
        {err_box}
        <form method="POST" action="/login">
            <div class="form-group">
                <label class="form-label" for="email">Email</label>
                <input class="form-input" id="email" name="email" type="email" placeholder="admin@supportdesk.local" required />
            </div>
            <div class="form-group">
                <label class="form-label" for="password">Password</label>
                <input class="form-input" id="password" name="password" type="password" required />
            </div>
            <button class="btn btn-primary" id="login-btn" type="submit" style="width: 100%;">Sign In</button>
        </form>
    </div>
    """
    return render_page("Sign In", content)


@app.post("/login")
def login_post(
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password, role FROM users WHERE email = ?", (email.strip().lower(),))
    user = cursor.fetchone()

    if not user or user["password"] != password:
        conn.close()
        return RedirectResponse(url="/login?error=Invalid+email+or+password", status_code=status.HTTP_303_SEE_OTHER)

    session_id = secrets.token_hex(24)
    cursor.execute(
        "INSERT INTO sessions (session_id, user_id, created_at) VALUES (?, ?, ?)",
        (session_id, user["id"], datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    resp = RedirectResponse(url="/tickets", status_code=status.HTTP_303_SEE_OTHER)
    resp.set_cookie(key="session_id", value=session_id, httponly=True)
    return resp


@app.get("/logout")
def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        conn = get_connection()
        conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        conn.close()

    resp = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    resp.delete_cookie("session_id")
    return resp


@app.get("/tickets")
def list_tickets(
    request: Request,
    q: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    user = get_current_user_from_req(request)
    if not user:
        return RedirectResponse(url="/login")

    settings = get_settings()
    conn = get_connection()
    cursor = conn.cursor()

    sql = "SELECT id, title, description, priority, status, customer_email, assignee, created_at FROM tickets WHERE 1=1"
    params = []

    if status_filter:
        sql += " AND status = ?"
        params.append(status_filter.upper())

    if q and q.strip():
        search_term = q.strip()
        # DEFECT 3: If defects_enabled, ID search fails to match!
        if search_term.isdigit() or search_term.startswith("#"):
            clean_id = search_term.lstrip("#")
            if settings.defects_enabled:
                # Planted defect: intentionally break ID search by checking id = -9999
                sql += " AND id = -9999"
            else:
                sql += " AND id = ?"
                params.append(int(clean_id))
        else:
            sql += " AND title LIKE ?"
            params.append(f"%{search_term}%")

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    tickets = cursor.fetchall()
    conn.close()

    rows = ""
    for t in tickets:
        p_badge = f"badge-{t['priority'].lower()}"
        s_badge = f"badge-{t['status'].lower().replace('_', '')}"
        rows += f"""
        <tr id="ticket-row-{t['id']}">
            <td><a href="/tickets/{t['id']}" id="ticket-id-link-{t['id']}" style="font-weight: 600; color: #4F46E5;">#{t['id']}</a></td>
            <td><a href="/tickets/{t['id']}" style="color: inherit; text-decoration: none;" id="ticket-title-{t['id']}">{t['title']}</a></td>
            <td><span class="badge {p_badge}" id="ticket-priority-badge-{t['id']}">{t['priority']}</span></td>
            <td><span class="badge {s_badge}" id="ticket-status-badge-{t['id']}">{t['status']}</span></td>
            <td>{t['customer_email']}</td>
            <td>{t['assignee'] or '<span style="color: #94A3B8;">Unassigned</span>'}</td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="6" style="text-align: center; color: #64748B; padding: 32px;" id="no-tickets-msg">No tickets found.</td></tr>'

    content = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <h2>Support Tickets</h2>
        <a href="/tickets/new" class="btn btn-primary" id="new-ticket-btn">+ Create Ticket</a>
    </div>

    <div class="card" style="padding: 16px; margin-bottom: 16px;">
        <form method="GET" action="/tickets" style="display: flex; gap: 12px; align-items: center;">
            <input class="form-input" type="text" name="q" id="search-input" placeholder="Search by title or ID (e.g. #1 or Bug)..." value="{q or ''}" style="flex: 1;" />
            <select class="form-select" name="status_filter" id="status-filter" style="width: 160px;">
                <option value="">All Statuses</option>
                <option value="OPEN" {'selected' if status_filter == 'OPEN' else ''}>OPEN</option>
                <option value="IN_PROGRESS" {'selected' if status_filter == 'IN_PROGRESS' else ''}>IN PROGRESS</option>
                <option value="RESOLVED" {'selected' if status_filter == 'RESOLVED' else ''}>RESOLVED</option>
                <option value="CLOSED" {'selected' if status_filter == 'CLOSED' else ''}>CLOSED</option>
            </select>
            <button class="btn btn-secondary" id="search-btn" type="submit">Filter</button>
            <a href="/tickets" class="btn btn-secondary" style="color: #64748B;">Reset</a>
        </form>
    </div>

    <div class="card" style="padding: 0; overflow-x: auto;">
        <table>
            <thead>
                <tr>
                    <th style="width: 80px;">ID</th>
                    <th>Title</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Customer</th>
                    <th>Assignee</th>
                </tr>
            </thead>
            <tbody id="ticket-table-body">
                {rows}
            </tbody>
        </table>
    </div>
    """
    return render_page("Tickets", content, user=user)


@app.get("/tickets/new")
def new_ticket_page(request: Request):
    user = get_current_user_from_req(request)
    if not user:
        return RedirectResponse(url="/login")

    content = """
    <div class="card" style="max-width: 600px; margin: 0 auto;">
        <h2 style="margin-bottom: 16px;">Create Support Ticket</h2>
        <form method="POST" action="/tickets/new">
            <div class="form-group">
                <label class="form-label" for="title">Title *</label>
                <input class="form-input" id="title" name="title" placeholder="Brief summary of the issue" required />
            </div>
            <div class="form-group">
                <label class="form-label" for="customer_email">Customer Email *</label>
                <input class="form-input" id="customer_email" name="customer_email" type="email" placeholder="customer@example.com" required />
            </div>
            <div class="form-group">
                <label class="form-label" for="priority">Priority *</label>
                <select class="form-select" id="priority" name="priority">
                    <option value="Low">Low</option>
                    <option value="Medium" selected>Medium</option>
                    <option value="High">High</option>
                </select>
            </div>
            <div class="form-group">
                <label class="form-label" for="description">Description *</label>
                <textarea class="form-textarea" id="description" name="description" rows="4" placeholder="Detailed description of the issue..." required></textarea>
            </div>
            <div style="display: flex; gap: 8px;">
                <button class="btn btn-primary" id="submit-ticket-btn" type="submit">Create Ticket</button>
                <a href="/tickets" class="btn btn-secondary">Cancel</a>
            </div>
        </form>
    </div>
    """
    return render_page("Create Ticket", content, user=user)


@app.post("/tickets/new")
def create_ticket_post(
    request: Request,
    title: str = Form(...),
    customer_email: str = Form(...),
    priority: str = Form(...),
    description: str = Form(...),
):
    require_auth(request)
    settings = get_settings()

    # DEFECT 2: If defects_enabled, High priority is persisted incorrectly as Low!
    persisted_priority = priority
    if settings.defects_enabled and priority.lower() == "high":
        persisted_priority = "Low"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tickets (title, description, priority, status, customer_email, assignee, created_at)
        VALUES (?, ?, ?, 'OPEN', ?, NULL, ?)
    """, (
        title.strip(),
        description.strip(),
        persisted_priority,
        customer_email.strip(),
        datetime.now(timezone.utc).isoformat(),
    ))
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return RedirectResponse(url=f"/tickets/{new_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/tickets/{ticket_id}")
def view_ticket(request: Request, ticket_id: int):
    user = get_current_user_from_req(request)
    if not user:
        return RedirectResponse(url="/login")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cursor.fetchone()
    conn.close()

    if not ticket:
        return render_page("Not Found", '<div class="card" id="ticket-not-found"><h2>Ticket not found</h2><p><a href="/tickets">Back to tickets</a></p></div>', user=user)

    content = f"""
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div>
            <a href="/tickets" style="color: #4F46E5; text-decoration: none; font-size: 13px;">&larr; Back to Tickets</a>
            <h1 style="margin-top: 4px;" id="ticket-title">#{ticket['id']} - {ticket['title']}</h1>
        </div>
        <div>
            <form method="POST" action="/tickets/{ticket['id']}/delete" style="display: inline;" onsubmit="return confirm('Permanently delete ticket?');">
                <button class="btn btn-danger" id="delete-ticket-btn" type="submit">Delete Ticket</button>
            </form>
        </div>
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 24px;">
        <div class="card">
            <h3 style="margin-bottom: 12px; font-size: 15px;">Description</h3>
            <p style="white-space: pre-wrap; font-size: 14px; color: #334155;" id="ticket-desc">{ticket['description']}</p>
        </div>

        <div class="card">
            <h3 style="margin-bottom: 16px; font-size: 15px;">Ticket Details</h3>
            <div style="margin-bottom: 12px; font-size: 13px;">
                <span style="color: #64748B;">Priority:</span>
                <span class="badge badge-{ticket['priority'].lower()}" id="detail-priority">{ticket['priority']}</span>
            </div>
            <div style="margin-bottom: 12px; font-size: 13px;">
                <span style="color: #64748B;">Customer:</span>
                <span id="detail-customer">{ticket['customer_email']}</span>
            </div>
            <div style="margin-bottom: 16px; font-size: 13px;">
                <span style="color: #64748B;">Created:</span>
                <span>{ticket['created_at'][:19]}</span>
            </div>

            <hr style="border: 0; border-top: 1px solid #E2E8F0; margin: 16px 0;" />

            <form method="POST" action="/tickets/{ticket['id']}/update">
                <div class="form-group">
                    <label class="form-label" for="update-status">Status</label>
                    <select class="form-select" id="update-status" name="status">
                        <option value="OPEN" {'selected' if ticket['status'] == 'OPEN' else ''}>OPEN</option>
                        <option value="IN_PROGRESS" {'selected' if ticket['status'] == 'IN_PROGRESS' else ''}>IN PROGRESS</option>
                        <option value="RESOLVED" {'selected' if ticket['status'] == 'RESOLVED' else ''}>RESOLVED</option>
                        <option value="CLOSED" {'selected' if ticket['status'] == 'CLOSED' else ''}>CLOSED</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label" for="update-assignee">Assignee</label>
                    <select class="form-select" id="update-assignee" name="assignee">
                        <option value="">Unassigned</option>
                        <option value="admin@supportdesk.local" {'selected' if ticket['assignee'] == 'admin@supportdesk.local' else ''}>Admin</option>
                        <option value="agent@supportdesk.local" {'selected' if ticket['assignee'] == 'agent@supportdesk.local' else ''}>Agent</option>
                    </select>
                </div>
                <button class="btn btn-primary" id="update-ticket-btn" type="submit" style="width: 100%;">Update Ticket</button>
            </form>
        </div>
    </div>
    """
    return render_page(f"Ticket #{ticket['id']}", content, user=user)


@app.post("/tickets/{ticket_id}/update")
def update_ticket(
    request: Request,
    ticket_id: int,
    status: str = Form(...),
    assignee: Optional[str] = Form(None),
):
    require_auth(request)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE tickets SET status = ?, assignee = ? WHERE id = ?
    """, (status, assignee or None, ticket_id))
    conn.commit()
    conn.close()
    return RedirectResponse(url=f"/tickets/{ticket_id}", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/tickets/{ticket_id}/delete")
def delete_ticket(request: Request, ticket_id: int):
    user = require_auth(request)
    settings = get_settings()

    # DEFECT 1: If defects_enabled, support agent CAN delete!
    # If not defects_enabled, only admin can delete.
    if not settings.defects_enabled:
        if user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only administrators can delete tickets",
            )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()

    return RedirectResponse(url="/tickets", status_code=status.HTTP_303_SEE_OTHER)


# REST API endpoints for automated test execution
@app.post("/api/login")
def api_login(data: dict):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, password, role FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()

    if not user or user["password"] != password:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid email or password")

    session_id = secrets.token_hex(24)
    cursor.execute(
        "INSERT INTO sessions (session_id, user_id, created_at) VALUES (?, ?, ?)",
        (session_id, user["id"], datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()

    return {
        "access_token": session_id,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"], "role": user["role"]},
    }


@app.get("/api/tickets")
def api_list_tickets(
    request: Request,
    q: Optional[str] = None,
    status: Optional[str] = None,
    status_filter: Optional[str] = None,
):
    require_auth(request)
    settings = get_settings()
    conn = get_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM tickets WHERE 1=1"
    params = []

    filter_status = status or status_filter
    if filter_status and filter_status.strip():
        sql += " AND status = ?"
        params.append(filter_status.strip().upper())


    if q and q.strip():
        search_term = q.strip()
        if search_term.isdigit() or search_term.startswith("#"):
            clean_id = search_term.lstrip("#")
            if settings.defects_enabled:
                sql += " AND id = -9999"
            else:
                sql += " AND id = ?"
                params.append(int(clean_id))
        else:
            sql += " AND title LIKE ?"
            params.append(f"%{search_term}%")

    sql += " ORDER BY id DESC"
    cursor.execute(sql, params)
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


@app.post("/api/tickets", status_code=201)
def api_create_ticket(request: Request, data: dict):
    require_auth(request)
    settings = get_settings()

    priority = data.get("priority", "Medium")
    if settings.defects_enabled and priority.lower() == "high":
        priority = "Low"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO tickets (title, description, priority, status, customer_email, assignee, created_at)
        VALUES (?, ?, ?, 'OPEN', ?, NULL, ?)
    """, (
        data.get("title", ""),
        data.get("description", ""),
        priority,
        data.get("customer_email", ""),
        datetime.now(timezone.utc).isoformat(),
    ))
    new_id = cursor.lastrowid
    conn.commit()
    cursor.execute("SELECT * FROM tickets WHERE id = ?", (new_id,))
    ticket = dict(cursor.fetchone())
    conn.close()
    return ticket


@app.delete("/api/tickets/{ticket_id}", status_code=204)
def api_delete_ticket(request: Request, ticket_id: int):
    user = require_auth(request)
    settings = get_settings()

    if not settings.defects_enabled:
        if user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only administrators can delete tickets",
            )

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    return None
