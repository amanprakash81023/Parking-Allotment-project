from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable

def generate_normal_pdf(filename="Parking_Project_Overview.pdf"):
    doc = SimpleDocTemplate(
        filename,
        pagesize=letter,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'MainTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1A202C'),
        spaceAfter=6
    )

    subtitle_style = ParagraphStyle(
        'SubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#4A5568'),
        spaceAfter=12
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=colors.HexColor('#2B6CB0'),
        spaceBefore=12,
        spaceAfter=6
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#2D3748'),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Normal_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=15,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#805AD5'),
        spaceAfter=4
    )

    story = []

    # Title
    story.append(Paragraph("Parking Allotment Backend — Project Guide", title_style))
    story.append(Paragraph("Simple & Comprehensive Overview for Technical Interview & System Defense", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E0'), spaceAfter=10))

    # Section 1: What is this project?
    story.append(Paragraph("1. System Overview", h1_style))
    story.append(Paragraph("A REST API built with <b>FastAPI</b> and <b>PostgreSQL</b> for a multi-floor parking facility. It handles vehicle registration, smart slot allocation by preference, slot release with duration calculation, and real-time occupancy tracking.", body_style))
    story.append(Paragraph("<b>The 3 Core Concepts:</b>", h2_style))
    story.append(Paragraph("• <b>Slot:</b> A physical parking space (e.g. A-1, B-10), typed as BIKE, CAR, or EV, either AVAILABLE or OCCUPIED.", bullet_style))
    story.append(Paragraph("• <b>Vehicle:</b> A registered vehicle with an uppercase license plate, owner name, and type.", bullet_style))
    story.append(Paragraph("• <b>Allocation:</b> The record linking a vehicle to a slot with entry/exit timestamps and status (ACTIVE / RELEASED).", bullet_style))

    story.append(Spacer(1, 4))

    # Section 2: API Endpoints
    story.append(Paragraph("2. The 7 API Endpoints", h1_style))
    story.append(Paragraph("• <b>POST /slots (201):</b> Creates a parking slot with format &lt;FLOOR&gt;-&lt;NUMBER&gt; (e.g. A-1, B-10). Returns 409 if duplicate.", bullet_style))
    story.append(Paragraph("• <b>GET /slots (200):</b> Lists all slots in numeric order. Optional filters by status and type.", bullet_style))
    story.append(Paragraph("• <b>POST /vehicles (201):</b> Registers a vehicle plate. Returns 409 if already registered.", bullet_style))
    story.append(Paragraph("• <b>GET /vehicles (200):</b> Lists all registered vehicles with current slot and is_parked status (Single query, no N+1).", bullet_style))
    story.append(Paragraph("• <b>POST /allocate (201):</b> Automatically allots the lowest available compatible slot.", bullet_style))
    story.append(Paragraph("• <b>POST /release (200):</b> Frees the slot and computes parking duration in minutes (rounded up).", bullet_style))
    story.append(Paragraph("• <b>GET /allocations (200):</b> Lists active parking sessions ordered by newest first.", bullet_style))

    story.append(Spacer(1, 4))

    # Section 3: Core Business Rules
    story.append(Paragraph("3. Essential Business Rules", h1_style))
    story.append(Paragraph("<b>A. Slot Ordering (§4.1):</b>", h2_style))
    story.append(Paragraph("Lowest floor first, then lowest numerical slot (A-1 &lt; A-2 &lt; A-9 &lt; A-10 &lt; A-100 &lt; B-1). Storing slot number as plain text causes alphabetical bugs ('A-10' before 'A-2'). We solved this by storing <code>floor</code> and <code>slot_num</code> (integer) in separate indexed database columns.", bullet_style))

    story.append(Paragraph("<b>B. Vehicle Preferences (§4.2):</b>", h2_style))
    story.append(Paragraph("• <b>BIKE:</b> Only parks in BIKE slots.", bullet_style))
    story.append(Paragraph("• <b>CAR:</b> Only parks in CAR slots (never in EV slots; chargers are reserved).", bullet_style))
    story.append(Paragraph("• <b>EV:</b> Prefers EV slots; if full, falls back to CAR slots (does not charge).", bullet_style))

    story.append(Paragraph("<b>C. Concurrency Control (§4.4):</b>", h2_style))
    story.append(Paragraph("To prevent two concurrent requests from taking the same slot at the same millisecond, we use <b>Row-Level Locking</b> (<code>SELECT ... FOR UPDATE</code>) combined with <b>Database Partial Unique Indexes</b> (<code>WHERE status = 'ACTIVE'</code>).", bullet_style))

    story.append(Paragraph("<b>D. Error Envelope (§5.8):</b>", h2_style))
    story.append(Paragraph("All non-2xx responses use the identical JSON structure: <code>{ \"error\": { \"code\": \"...\", \"message\": \"...\", \"details\": null } }</code>.", bullet_style))

    story.append(Spacer(1, 4))

    # Section 4: Key Interview Questions
    story.append(Paragraph("4. Technical Interview Defense ('What Breaks If We Delete This Line?')", h1_style))
    story.append(Paragraph("• <b>query = query.with_for_update():</b> Without row locking, parallel requests read the same free slot simultaneously, leading to double booking race conditions.", bullet_style))
    story.append(Paragraph("• <b>CREATE UNIQUE INDEX ... WHERE status = 'ACTIVE':</b> Enforces database-level authority so no vehicle or slot can ever hold two active parkings at the same time.", bullet_style))
    story.append(Paragraph("• <b>v = v.strip().upper():</b> Guarantees plate normalization so 'mh12ab1234' and 'MH12AB1234' are treated as the exact same vehicle.", bullet_style))
    story.append(Paragraph("• <b>duration_minutes = max(1, math.ceil(delta / 60)):</b> Ensures parking duration is rounded up to whole minutes as required by the specification.", bullet_style))

    story.append(Spacer(1, 4))

    # Section 5: Commands
    story.append(Paragraph("5. Quick Commands", h1_style))
    story.append(Paragraph("• <b>Start App:</b> <code>python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload</code>", bullet_style))
    story.append(Paragraph("• <b>Run Tests:</b> <code>python -m pytest -v</code> (22/22 tests passing)", bullet_style))
    story.append(Paragraph("• <b>Swagger Docs:</b> <code>http://localhost:8000/docs</code>", bullet_style))

    doc.build(story)
    print(f"Generated clean PDF: {filename}")

if __name__ == "__main__":
    generate_normal_pdf()
