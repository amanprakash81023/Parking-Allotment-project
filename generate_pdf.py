import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable

def create_cheatsheet_pdf(filename="Parking_Backend_Interview_CheatSheet.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=4
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4a5568'),
        spaceAfter=10
    )
    
    h1_style = ParagraphStyle(
        'SectionH1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2b6cb0'),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2d3748')
    )

    bold_body_style = ParagraphStyle(
        'BoldBody',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1a202c')
    )

    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#9b2c2c')
    )

    story = []

    # Title & Header
    story.append(Paragraph("Parking Allotment Backend — Interview Quick Guide", title_style))
    story.append(Paragraph("FastAPI + PostgreSQL | Core Architecture, Concurrency & Defense Cheatsheet", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#3182ce'), spaceAfter=8))

    # Section 1: Domain & API Surface
    story.append(Paragraph("1. System Concepts & Endpoints", h1_style))
    
    api_data = [
        [Paragraph("<b>Endpoint</b>", bold_body_style), Paragraph("<b>Method</b>", bold_body_style), Paragraph("<b>Purpose & Key Rule</b>", bold_body_style), Paragraph("<b>Status</b>", bold_body_style)],
        [Paragraph("/slots", code_style), Paragraph("POST", body_style), Paragraph("Register slot with format &lt;FLOOR&gt;-&lt;NUM&gt; (e.g. A-1). Check duplicate.", body_style), Paragraph("201 / 409 / 422", body_style)],
        [Paragraph("/slots", code_style), Paragraph("GET", body_style), Paragraph("List slots ordered numerically (A-1 &lt; A-2 &lt; A-10 &lt; B-1). Filter by status/type.", body_style), Paragraph("200 / 422", body_style)],
        [Paragraph("/vehicles", code_style), Paragraph("POST", body_style), Paragraph("Register vehicle plate (normalized uppercase), owner, and type.", body_style), Paragraph("201 / 409 / 422", body_style)],
        [Paragraph("/vehicles", code_style), Paragraph("GET", body_style), Paragraph("List vehicles with <code>is_parked</code> & <code>current_slot</code> (Single LEFT JOIN, no N+1).", body_style), Paragraph("200", body_style)],
        [Paragraph("/allocate", code_style), Paragraph("POST", body_style), Paragraph("Assigns best free slot based on vehicle preference & row lock.", body_style), Paragraph("201 / 400 / 409", body_style)],
        [Paragraph("/release", code_style), Paragraph("POST", body_style), Paragraph("Frees slot, marks RELEASED, calculates <code>duration_minutes</code> rounded up.", body_style), Paragraph("200 / 404 / 409", body_style)],
        [Paragraph("/allocations", code_style), Paragraph("GET", body_style), Paragraph("Lists active/released sessions sorted descending by entry time.", body_style), Paragraph("200 / 422", body_style)]
    ]
    t_api = Table(api_data, colWidths=[75, 50, 320, 85])
    t_api.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#ebf8ff')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_api)
    story.append(Spacer(1, 6))

    # Section 2: Key Algorithms & Decisions
    story.append(Paragraph("2. Core Engineering Decisions", h1_style))
    
    decisions = [
        [Paragraph("<b>Topic</b>", bold_body_style), Paragraph("<b>The Problem</b>", bold_body_style), Paragraph("<b>The Solution Implemented</b>", bold_body_style)],
        [
            Paragraph("<b>Slot Ordering (§4.1)</b>", body_style),
            Paragraph("Text sorting puts 'A-10' before 'A-2' (lexicographical bug).", body_style),
            Paragraph("Split into separate columns: <code>floor (VARCHAR)</code> + <code>slot_num (INT)</code> with composite B-Tree index.", body_style)
        ],
        [
            Paragraph("<b>Vehicle Preferences (§4.2)</b>", body_style),
            Paragraph("Cars cannot take EV slots. EVs prefer EV slots but can fallback.", body_style),
            Paragraph("Preference list priority: <code>BIKE &rarr; [BIKE]</code>, <code>CAR &rarr; [CAR]</code>, <code>EV &rarr; [EV, CAR]</code>.", body_style)
        ],
        [
            Paragraph("<b>Concurrency (§4.4)</b>", body_style),
            Paragraph("Parallel allocations race for the same free slot.", body_style),
            Paragraph("1. Row lock: <code>SELECT ... FOR UPDATE</code><br/>2. DB Partial Unique Index: <code>WHERE status = 'ACTIVE'</code>.", body_style)
        ],
        [
            Paragraph("<b>No N+1 Queries (§5.4)</b>", body_style),
            Paragraph("Fetching current slot per vehicle usually fires N extra queries.", body_style),
            Paragraph("Single query with <code>LEFT OUTER JOIN</code> on active allocations and slots.", body_style)
        ],
        [
            Paragraph("<b>Error Envelope (§5.8)</b>", body_style),
            Paragraph("FastAPI default validation error leaks internals and non-standard JSON.", body_style),
            Paragraph("Global exception handlers returning uniform envelope: <code>{error: {code, message, details}}</code>.", body_style)
        ]
    ]
    t_dec = Table(decisions, colWidths=[105, 175, 250])
    t_dec.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#edf2f7')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_dec)
    story.append(Spacer(1, 8))

    # Page Break for Clean 2-Page Layout
    story.append(PageBreak())

    # Page 2: Interview Review Call Defense ("What Breaks If We Delete This Line?")
    story.append(Paragraph("3. Interview Defense: 'What Breaks If We Delete This Line?'", h1_style))
    story.append(Paragraph("Be prepared to explain these exact critical lines during the technical review:", subtitle_style))

    qna_data = [
        [Paragraph("<b>Code Snippet & Location</b>", bold_body_style), Paragraph("<b>Technical Explanation & Failure Impact</b>", bold_body_style)],
        [
            Paragraph("<code>query = query.with_for_update()</code><br/><i>(app/services.py)</i>", code_style),
            Paragraph("<b>Prevents concurrent race conditions.</b> Without row locking, concurrent transactions read the same available slot simultaneously, causing double allocations or transaction rollback errors.", body_style)
        ],
        [
            Paragraph("<code>CREATE UNIQUE INDEX ... WHERE status = 'ACTIVE'</code><br/><i>(schema.sql / models.py)</i>", code_style),
            Paragraph("<b>Database-level single active allocation guarantee.</b> If application checks fail or direct DB writes occur, the database acts as the ultimate authority rejecting duplicate active parkings.", body_style)
        ],
        [
            Paragraph("<code>v = v.strip().upper()</code><br/><i>(app/schemas.py)</i>", code_style),
            Paragraph("<b>Enforces plate normalization.</b> Without this, 'mh12ab1234' and 'MH12AB1234' would be treated as two different vehicles, violating §4.6 uniqueness.", body_style)
        ],
        [
            Paragraph("<code>math.ceil(delta_seconds / 60)</code><br/><i>(app/services.py)</i>", code_style),
            Paragraph("<b>Duration rounding up.</b> Guarantees any partial minute counts as a full minute per specification rules (e.g. 61 seconds = 2 minutes).", body_style)
        ],
        [
            Paragraph("<code>order_by(Slot.floor.asc(), Slot.slot_num.asc())</code><br/><i>(app/services.py)</i>", code_style),
            Paragraph("<b>Guarantees §4.1 slot prioritization.</b> Ensures A-2 is allotted before A-10 and floor A is prioritized before floor B.", body_style)
        ]
    ]
    t_qna = Table(qna_data, colWidths=[180, 350])
    t_qna.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#feebc8')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_qna)
    story.append(Spacer(1, 10))

    # Section 4: Quick Testing & Run Commands
    story.append(Paragraph("4. Quick Reference Commands", h1_style))
    cmd_data = [
        [Paragraph("<b>Action</b>", bold_body_style), Paragraph("<b>Command</b>", bold_body_style)],
        [Paragraph("Run Local Server", body_style), Paragraph("<code>python -m uvicorn app.main:app --reload</code>", code_style)],
        [Paragraph("Run Full Test Suite (TC01–TC14)", body_style), Paragraph("<code>python -m pytest -v</code>", code_style)],
        [Paragraph("Docker Compose Start", body_style), Paragraph("<code>docker compose up -d --build</code>", code_style)],
        [Paragraph("Swagger UI", body_style), Paragraph("<b>http://localhost:8000/docs</b>", body_style)]
    ]
    t_cmd = Table(cmd_data, colWidths=[160, 370])
    t_cmd.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_cmd)

    doc.build(story)
    print(f"Generated PDF: {filename}")

if __name__ == "__main__":
    create_cheatsheet_pdf()
